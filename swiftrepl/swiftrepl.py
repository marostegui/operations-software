#!/usr/bin/python

# Written by Mark Bergsma <mark@wikimedia.org>

import argparse
import collections
import ConfigParser
import errno
import httplib
import random
import re
import socket
import sys
import threading
import time
import traceback

import cloudfiles
import cloudfiles.errors
from cloudfiles.utils import unicode_quote

from Queue import Queue, LifoQueue, Empty, Full


copy_headers = re.compile(r'^X-Content-Duration$', flags=re.IGNORECASE)

NOBJECT = 1000
LIMIT_MAX = 10000

src = {}
dst = {}
options = None
containers = []

class WorkingConnectionPool(cloudfiles.connection.ConnectionPool):
    def __init__(self, username=None, api_key=None, **kwargs):
        self.connargs = dict(kwargs)
        self.connargs.update({'username': username, 'api_key': api_key})
        self.timeout = kwargs.get('timeout', 5)
        poolsize = kwargs.get('poolsize', 10)
        Queue.__init__(self, poolsize)

def connect(params):
    return WorkingConnectionPool(username=(params['username'] or None),
                                 api_key=(params['api_key'] or None),
                                 authurl=params['auth_url'],
                                 timeout=60,
                                 poolsize=options.threads * 4)

def varnish_rewrite(obj):
    match = re.match(r'^(?P<proj>[^\-]+)-(?P<lang>[^\-]+)-(?P<repo>[^\-]+)-(?P<zone>[^\-\.]+)(\..*)?$', obj.container.name)
    if match:
        host = 'upload.wikimedia.org'
        uri = '/%s/%s/%s/%s' % (match.group('proj'), match.group('lang'), match.group('zone'), unicode_quote(obj.name))
        return host, uri
    else:
        raise cloudfiles.errors.InvalidContainerName()

def varnish_object_stream_prepare(obj):
    obj._name_check()
    host, uri = varnish_rewrite(obj)
    headers = {
        'User-Agent': "swiftrepl",
        'If-Cached': obj.etag
    }

    try:
        varnish_object_stream_prepare.queue
    except AttributeError:
        varnish_object_stream_prepare.queue = LifoQueue(maxsize=256)

    try:
        connection, t = varnish_object_stream_prepare.queue.get(False)
        if time.time() - t > 3:
            raise Empty()
    except Empty:
        connection = httplib.HTTPConnection(host, port=80, timeout=10)

    connection.request('GET', uri, None, headers)
    response = connection.getresponse()
    if response.status < 200 or response.status > 299:
        buff = response.read()
        try:
            varnish_object_stream_prepare.queue.put((connection, time.time()), False)
        except Full:
            del connection
        raise cloudfiles.errors.ResponseError(response.status, response.reason)
    return response, connection

def object_stream_prepare(obj, hdrs=None):
    obj._name_check()
    response = obj.container.conn.make_request('GET',
                                               path=[obj.container.name,
                                                     obj.name], hdrs=hdrs)
    if response.status < 200 or response.status > 299:
        buff = response.read()
        raise cloudfiles.errors.ResponseError(response.status, response.reason)
    return response

def object_stream(response, chunksize=8192):
    buff = response.read(chunksize)
    while len(buff) > 0:
        yield buff
        buff = response.read(chunksize)
    # I hate you httplib
    buff = response.read()

def copy_metadata(response, dstobj, headers={}):
    global copy_headers

    for hdr in response.getheaders():
        if copy_headers.match(hdr[0]):
            hdrname = "-".join([seg.capitalize() for seg in hdr[0].split("-")])
            headers[hdrname] = hdr[1]
            print "Copying custom header", hdrname, hdr[1]
        elif hdr[0].lower().startswith('x-object-meta-'):
            dstobj.metadata[hdr[0][14:]] = hdr[1]

def send_object(dstobj, iterable, headers={}):
    """
    Imported and modified from cloudfiles.storage_object.Object.send,
    to allow specifying custom headers
    """
    assert dstobj.size is not None

    if not dstobj.content_type:
        dstobj.content_type = 'application/octet-stream'

    path = "/%s/%s/%s" % (dstobj.container.conn.uri.rstrip('/'),
                          unicode_quote(dstobj.container.name),
                          unicode_quote(dstobj.name))
    headers.update(dstobj._make_headers())

    headers['X-Auth-Token'] = dstobj.container.conn.token
    headers['User-Agent'] = dstobj.container.conn.user_agent
    http = dstobj.container.conn.connection
    http.putrequest('PUT', path)
    for key, value in headers.iteritems():
        http.putheader(key, value)
    http.endheaders()

    response = None
    transferred = 0
    try:
        for chunk in iterable:
            http.send(chunk)
            transferred += len(chunk)
        # If the generator didn't yield enough data, stop, drop, and roll.
        if transferred < dstobj.size:
            # possible cause: source's container listing has different size than actual file
            print >> sys.stderr, "%s %s incomplete send: transferred %d/%d" % \
                (dstobj.container.name, dstobj.name, transferred, dstobj.size)
            raise cloudfiles.errors.IncompleteSend()
        response = http.getresponse()
        buff = response.read()
    except socket.timeout, err:
        if response:
            # pylint: disable-msg=E1101
            response.read()
        raise err

    if (response.status < 200) or (response.status > 299):
        raise cloudfiles.errors.ResponseError(response.status, response.reason)

    for hdr in response.getheaders():
        if hdr[0].lower() == 'etag':
            dstobj._etag = hdr[1]

def replicate_object(srcobj, dstobj, srcconnpool, dstconnpool):
    # Replace the connections
    srcobj.container.conn = srcconnpool.get()
    dstobj.container.conn = dstconnpool.get()

    self = replicate_object

    try:
        for i in range(3):
            try:
                self.count += 1
                connection = None
                if options.use_varnish:
                    # Try Varnish first
                    try:
                        response, connection = varnish_object_stream_prepare(srcobj)
                        self.hits += 1
                    except:
                        connection = None
                if not options.use_varnish or connection is None:
                    # Start source GET request
                    response = object_stream_prepare(srcobj)

                dstobj.content_type = srcobj.content_type
                dstobj.etag = srcobj.etag
                dstobj.last_modified = srcobj.last_modified
                dstobj.size = srcobj.size
                dstobj.metadata = dict(srcobj.metadata)
                headers = {}
                copy_metadata(response, dstobj, headers)
                send_object(dstobj, object_stream(response, chunksize=65536), headers)

                if connection is not None:
                    try:
                        varnish_object_stream_prepare.queue.put((connection, time.time()), False)
                    except Full:
                        del connection

            except httplib.CannotSendRequest as e:
                srcobj.container.conn = srcconnpool.get()
                dstobj.container.conn = dstconnpool.get()
                continue
            except (AttributeError, socket.error, httplib.ResponseNotReady, httplib.BadStatusLine) as e:
                # httplib bug?
                time.sleep(1)
                continue
            except cloudfiles.errors.ResponseError as e:
                if e.status == 404:
                    # File was deleted
                    pass
                else:
                    print "Error occurred, skipping"
                    print e
                    # FIXME
                break
            except Exception as e:
                continue
            else:
                break
        else:
            print >> sys.stderr, "Repeated error in replicate_object"
            raise
        srcconnpool.put(srcobj.container.conn)
        dstconnpool.put(dstobj.container.conn)
    finally:
        srcobj.container.conn, dstobj.container.conn = None, None

        if self.count % 100 == 0:
            pct = lambda x, y: y != 0 and int(float(x) / y * 100) or 0
            print ("VARNISH: %d/%d (%d%%)" %
                   (self.hits, self.count, pct(self.hits, self.count)))
# FIXME initialize
replicate_object.count = 0
replicate_object.hits = 0


def get_container_objects(container, limit, marker, connpool):

    container.conn = connpool.get()
    try:
        objects = None
        for i in range(3):
            try:
                objects = container.get_objects(limit=limit, marker=marker)
            except AttributeError as e:
                # httplib bug?
                continue
            except socket.timeout as e:
                continue
            except socket.error as e:
                if e.errno == errno.EAGAIN:
                    continue
                else:
                    print >> sys.stderr, e, traceback.format_exc()
                    continue
            except httplib.ResponseNotReady as e:
                time.sleep(1)
                continue
            except Exception as e:
                print >> sys.stderr, e, traceback.format_exc()
                continue
            else:
                return objects
        else:
            print >> sys.stderr, "Repeated error in get_container_objects"
            raise e
    finally:
        connpool.put(container.conn)
        container.conn = None

def create_container(dstconn, name):
    try:
        dstcontainer = dstconn.create_container(name)
    except Exception as e:
        print >> sys.stderr, "Could not create container", name
        raise e
    else:
        print "Created container", name

def sync_container(srccontainer, srcconnpool, dstconnpool, filename_regexp):

    last = ''
    hits, processed, gets, skipped = 0, 0, 0, 0

    dstconn = dstconnpool.get()
    try:
        try:
            dstcontainer = dstconn.get_container(srccontainer.name)
        except cloudfiles.errors.NoSuchContainer as e:
            create_container(dstconn, srccontainer.name)
            dstcontainer = dstconn.get_container(srccontainer.name)
    finally:
        dstconnpool.put(dstconn)
        dstconn = None

    dstobjects = None
    while True:
        srcobjects = get_container_objects(srccontainer, limit=NOBJECT, marker=last, connpool=srcconnpool)

        limit = NOBJECT
        while dstobjects is None or (len(dstobjects) >= limit and dstobjects[-1].name < srcobjects[-1].name):
            dstobjects = get_container_objects(dstcontainer, limit=limit, marker=last, connpool=dstconnpool)
            if len(dstobjects) == limit:
                limit *= 2
                if limit > LIMIT_MAX:
                    dstobjects = None
                    break

        for srcobj in srcobjects:
            objname = srcobj.name.encode("ascii", errors="ignore")
            if filename_regexp is not None and not filename_regexp.match(objname):
                skipped += 1
                continue
            processed += 1
            last = srcobj.name.encode("utf-8")
            msg = "%s\t%s\t%s\t%s\t%s" % (srccontainer.name, srcobj.etag, srcobj.size, objname, srcobj.last_modified)
            try:
                if dstobjects is not None:
                    dstobj = dstobjects[dstobjects.index(srcobj.name)]
                else:
                    gets += 1
                    dstcontainer.conn = dstconnpool.get()
                    try:
                        dstobj = dstcontainer.get_object(srcobj.name)
                    finally:
                        dstconnpool.put(dstcontainer.conn)
                        dstcontainer.conn = None
            except (ValueError, cloudfiles.errors.NoSuchObject) as e:
                #print msg
                #print "Destination does not have %s, syncing" % objname
                object_record = dict.fromkeys(['content_type', 'bytes', 'last_modified', 'hash'], None)
                object_record['name'] = srcobj.name
                dstobj = cloudfiles.storage_object.Object(dstcontainer, object_record=object_record)
            else:
                if srcobj.etag != dstobj.etag:
                    print "%s\t%s\tE-Tag mismatch: %s/%s, syncing" % (srccontainer.name, objname, srcobj.etag, dstobj.etag)
                else:
                    # Object already exists
                    hits += 1
                    continue

            replicate_object(srcobj, dstobj, srcconnpool, dstconnpool)

        pct = lambda x, y: y != 0 and int(float(x) / y * 100) or 0
        print ("STATS: %s processed: %d/%d (%d%%), hit rate: %d%%, skipped %d/%d (%d%%)" %
               (srccontainer.name,
                processed, srccontainer.object_count,
                pct(processed, srccontainer.object_count),
                pct(hits, processed),
                skipped, srccontainer.object_count,
                pct(skipped, srccontainer.object_count),
                ))

        if len(srcobjects) < NOBJECT:
            break

    print "FINISHED:", srccontainer.name

def sync_deletes_slow(srccontainer, srcconnpool, dstconnpool):

    dstconn = dstconnpool.get()
    try:
        dstcontainer = dstconn.get_container(srccontainer.name)
    except cloudfiles.errors.NoSuchContainer as e:
        # Destination container doesn't exist; nothing to delete
        return
    finally:
        dstconnpool.put(dstconn)

    srccontainer.conn = srcconnpool.get()
    try:
        last = ''
        deletes, processed = 0, 0
        while True:
            dstobjects = get_container_objects(dstcontainer, limit=NOBJECT, marker=last, connpool=dstconnpool)
            for dstobj in dstobjects:
                processed += 1
                srccontainer.conn = srcconnpool.get()
                try:
                    srcobj = srccontainer.get_object(dstobj.name)   # Does a HEAD
                except cloudfiles.errors.NoSuchObject as e:
                    # File was deleted on the source
                    print "Deleting object", dstobj.name.encode("ascii", errors="ignore")

                    deletes += 1
                    dstcontainer.conn = dstconnpool.get()
                    try:
                        dstcontainer.delete_object(dstobj.name)
                    finally:
                        dstconnpool.put(dstcontainer.conn)
                        dstcontainer.conn = None

            last = dstobj.name.encode("utf-8")

            pct = lambda x, y: y != 0 and int(float(x) / y * 100) or 0
            print ("STATS: %s processed: %d/%d (%d%%), deleted: %d" %
                   (srccontainer.name,
                    processed, dstcontainer.object_count,
                    pct(processed, dstcontainer.object_count),
                    deletes))

            if len(dstobjects) < NOBJECT:
                break
        print "FINISHED:", srccontainer.name
    finally:
        srcconnpool.put(srccontainer.conn)
        srccontainer.conn = None

def sync_deletes(srccontainer, srcconnpool, dstconnpool, filename_regexp):

    dstconn = dstconnpool.get()
    try:
        dstcontainer = dstconn.get_container(srccontainer.name)
    except cloudfiles.errors.NoSuchContainer as e:
        # Destination container doesn't exist; nothing to delete
        return
    finally:
        dstconnpool.put(dstconn)

    srclimit = dstlimit = 5 * NOBJECT
    # fetch 20% more of source
    srclimit = int(srclimit * 1.2)

    last = ''
    deletes, processed, skipped = 0, 0, 0
    while True:

        dstobjects = get_container_objects(dstcontainer, limit=dstlimit, marker=last, connpool=dstconnpool)

        # bail-out early on empty containers
        if len(dstobjects) == 0:
            break

        srcobjects = get_container_objects(srccontainer, limit=srclimit, marker=last, connpool=srcconnpool)

        dstset = set([obj.name for obj in dstobjects])
        srcset = set([obj.name for obj in srcobjects])
        diff = dstset - srcset

        for dstname in diff:
            if filename_regexp is not None and not filename_regexp.match(dstname):
                skipped += 1
                continue
            # do a HEAD to make sure it's gone
            srccontainer.conn = srcconnpool.get()
            try:
                srcobj = srccontainer.get_object(dstname)   # Does a HEAD
            except cloudfiles.errors.NoSuchObject as e:
                # File was deleted on the source
                print "Deleting object", dstname.encode("ascii", errors="ignore")

                deletes += 1
                dstcontainer.conn = dstconnpool.get()
                try:
                    dstcontainer.delete_object(dstname)
                finally:
                    dstconnpool.put(dstcontainer.conn)
                    dstcontainer.conn = None
            finally:
                srcconnpool.put(srccontainer.conn)
                srccontainer.conn = None

        last = dstobjects[-1].name.encode("utf-8")
        processed += len(dstobjects)

        pct = lambda x, y: y != 0 and int(float(x) / y * 100) or 0
        print ("STATS: %s processed: %d/%d (%d%%), deleted: %d, skipped %d/%d (%d%%)" %
               (srccontainer.name,
                processed, dstcontainer.object_count,
                pct(processed, dstcontainer.object_count),
                deletes,
                skipped, dstcontainer.object_count,
                pct(skipped, dstcontainer.object_count),
                ))

        if len(dstobjects) < dstlimit:
            break
    print "FINISHED:", srccontainer.name

def replicator_thread(*args, **kwargs):
    while True:
        try:
            try:
                container = containers.popleft()
            except IndexError:
                break

            if options.sync_deletes:
                sync_deletes(container, kwargs['srcconnpool'],
                        kwargs['dstconnpool'], kwargs['filename_regexp'])
            else:
                sync_container(container, kwargs['srcconnpool'],
                        kwargs['dstconnpool'], kwargs['filename_regexp'])

            if not options.once:  # once
                containers.append(container)
        except Exception as e:
            print >> sys.stderr, e, traceback.format_exc()
            print >> sys.stderr, "Abandoning container %s for now" % container
            time.sleep(10)
            containers.append(container)


def parse_config(config_path):
    config = ConfigParser.SafeConfigParser()
    config.read(config_path)
    src = {}
    dst = {}
    container_sets = {}
    for option in 'username', 'api_key', 'auth_url':
        src[option] = config.get('src', option)
        dst[option] = config.get('dst', option)
    if config.has_section('container_sets'):
        container_sets = dict(config.items('container_sets'))
    return src, dst, container_sets


def main():
    global options, containers, src, dst

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config', default='swiftrepl.conf')
    parser.add_argument('--shuffle', '-r', dest='shuffle', action='store_true', default=False)
    parser.add_argument('--threads', '-t', dest='threads', type=int, default=16)
    parser.add_argument('--use-varnish', dest='use_varnish', action='store_true', default=False)
    parser.add_argument('--once', '-o', dest='once', action='store_true', default=False)
    parser.add_argument('--sync-deletes', '-d', dest='sync_deletes', action='store_true', default=False)
    parser.add_argument('--container-set', dest='container_set', metavar='SET')
    parser.add_argument('--container-regexp', dest='container_regexp', metavar='REGEXP')
    parser.add_argument('--filename-regexp', dest='filename_regexp', metavar='REGEXP')
    options = parser.parse_args()

    src, dst, container_sets = parse_config(options.config)

    if all([options.container_set, options.container_regexp]):
        parser.error('use only one of container-set or container-regexp')

    if not any([options.container_set, options.container_regexp]):
        parser.error('use at least one of container-set or container-regexp')

    container_regexp = options.container_regexp
    if options.container_regexp:
        container_regexp = options.container_regexp
    elif options.container_set:
        if not options.container_set in container_sets:
            parser.error('container set %s not found in config' % options.container_set)
        container_regexp = container_sets[options.container_set]

    filename_regexp = None
    if options.filename_regexp is not None:
        try:
            filename_regexp = re.compile(options.filename_regexp)
        except re.error as e:
            parser.error('cannot compile %r: %r' % (options.filename_regexp, e))

    srcconnpool = connect(src)
    dstconnpool = connect(dst)

    srcconn = srcconnpool.get()

    last = ''
    while True:
        page = srcconn.get_all_containers(limit=LIMIT_MAX, marker=last)
        if len(page) == 0:
            break
        last = page[-1].name.encode("utf-8")
        containers.extend(page)
        if len(page) < LIMIT_MAX:
            break

    containerlist = [container for container in containers
                     if re.match(container_regexp, container.name)]
    if options.shuffle:
        random.shuffle(containerlist)

    containers = collections.deque(containerlist)
    srcconnpool.put(srcconn)

    # Start threads
    for i in range(options.threads):
        t = threading.Thread(target=replicator_thread,
                             kwargs={'srcconnpool': srcconnpool,
                                     'dstconnpool': dstconnpool,
                                     'filename_regexp': filename_regexp})
        t.daemon = True
        t.start()

    for thread in threading.enumerate():
        if thread is threading.currentThread():
            continue
        thread.join()


if __name__ == '__main__':
    sys.exit(main())
