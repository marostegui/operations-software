import os
import sys

sys.path.append('/srv/audits/retention/scripts/')

import retention.utils
import retention.magic
from retention.config import Config
from retention.localfileaudit import LocalFilesAuditor
import retention.ignores

class LocalHomesAuditor(LocalFilesAuditor):
    '''
    auditing of home directories on a set of hosts

    users may have a local '.data_retention' file in their
    home directories with a list, on entry per line, of files
    or directories (dirs must end in '/') to skip during the audit
    '''

    def __init__(self, audit_type,
                 show_content=False, dirsizes=False,
                 depth=2, to_check=None, ignore_also=None, timeout=60,
                 maxfiles=None):
        '''
        see FilesAuditor for the arguments to the constructor
        '''
        super(LocalHomesAuditor, self).__init__(audit_type,
                                                show_content, dirsizes,
                                                depth, to_check, ignore_also,
                                                timeout, maxfiles)
        self.homes_owners = {}

        # FIXME where are these ever used???
        local_ignores = retention.ignores.get_local_ignores(self.locations)
        local_ignored_dirs, local_ignored_files = retention.ignores.process_local_ignores(
            local_ignores, self.ignores.ignored)
