class Config(object):
    '''
    directories and files to skip, where to look for files to be
    scanned, etc.
    change to suit your setup.
    '''

    cf = {
        'root_locations': ["/root"],
        'logs_locations': ["/var/log", "/a",
                           "/var/store"],
        'homes_locations': ["/home", "/data/db20/home"],

        'rotate_basedir': "/etc/logrotate.d",
        'rotate_mainconf': "/etc/logrotate.conf",

        'mysqlconf': ["/etc/mysql/my.cnf", "/etc/my.cnf"],

        # ignore these
        'ignored_dirs': {
            '*':
            [".aptitude", ".augeas",
             ".bash.completion.d",
             ".bazaar", "benchmarks",
             ".byobu", ".bzr",
             ".store", ".cassandra", ".cache",
             ".config", ".cpan",
             ".dbus",
             "deb", ".debug", ".debtags", ".drush",
             ".fontconfig", ".gconfd",
             ".gem", ".git",
             ".gnome", ".gnupg",
             "hadoop-benchmarks", ".hivehistory",
             ".ipython", ".irssi",
             ".jmxsh_history", ".kde",
             ".lftp", ".links2",
             ".liquidprompt", "mediawiki-config",
             ".mozilla", "novaclient",
             ".npm", ".oprofile",
             ".oozie-auth-token", ".pig_history",
             ".pip", ".puppet",
             ".ssh", "software",
             ".spamassassin", ".subversion",
             ".sunw", ".svn", ".texmf-var",
             ".w3m", ".wapi", ".vim"],

            '/var/log':
            ["anaconda", "apt", "atop", "dist-upgrade",
             "fsck", "ganeti/cleaner", "ganeti/master-cleaner",
             "hadoop-hdfs", "hadoop-yarn", "hive", "hhvm",
             "installer", "journal", "l10nupdatelog",
             "libvirt", "news", "ntpstats",
             "oozie", "samba", "src/pystatsd", "sysstat", "upstart",
             "wikidata", "zuul"],

            '/var/cache':
            ["abrt-di", "akmods", "apache2", "apt",
             "apt-show-versions", "apt-xapian-index",
             "archiva", "cups", "debconf", "dnf", "fontconfig",
             "fonts", "git", "jenkins/war", "jetty", "ldconfig",
             "lighttpd/compress", "man", "pbuilder",
             "planet", "pppconfig",
             "request-tracker4/mason_data",
             "salt", "samba", "smokeping/images", "svnusers", "yum"],

            '/a':
            ['mediawiki-config'],

            '/a/sqldata':
            ["*"],

            '/a/sqldata-cache':
            ["*"],

            '/srv/sqldata':
            ["*"],

            '/a/search':
            ["conf", "dumps", "indexes"]
        },
        'ignored_prefixes': [".bash_", ".xauth"],
        'ignored_files': {
            '*':
            [".ackrc", "apt.conf", "authorized_keys",
             ".bashrc",
             ".bconsole_history",
             "CmdTool.log", ".cshrc", ".cvspass",
             ".data_retention",
             ".emacs",
             ".exrc", ".forward",
             ".gdbinit", "gdbinit",
             ".gitconfig", ".gitignore",
             ".gitmodules", ".gitreview",
             ".gitignore_global", ".gnupg",
             ".gtkrc", ".hivehistory",
             ".hhvm.hhbc", ".hphpd.history",
             ".hphpd.ini",
             ".htoprc", ".hushlogin",
             ".inputrc", ".joe_state", ".joerc",
             ".lesshst", ".liquidpromptrc", "MegaSAS.log",
             ".mailcap", ".mh_profile",
             ".mime.types",
             ".mwsql_history",
             ".mweval_history", ".my.cnf",
             ".mysql_history", ".nano_history",
             ".npmrc",
             ".pearrc", ".pep8",
             ".php_history",
             ".pinerc", ".profile",
             "proxy-server.conf", "README",
             "README.txt",
             ".rediscli_history", ".rnd", ".screenrc",
             ".selected_editor", ".sh_history",
             "swift.conf", ".tcshrc",
             "__tokudb_lock_dont_delete_me_*",
             ".toprc", ".tramp_history",
             "twemproxy.conf", ".variables",
             ".vcl", ".viminfo", ".viminfo.tmp",
             ".vimrc", ".Xauthority",
             ".zshrc", ".zsh_history"],

            '/var/log':
            ["alternatives.log", "atop.log", "auth.log",
             "boot", "boot.log", "btmp", "daemon.log",
             "debug", "dmesg", "dnf.log",
             "dpkg.log", "faillog", "fontconfig.log", "fsck",
             "kern.log", "lastlog", "lpr.log", "messages",
             "puppet.log", "syslog", "udev", "ufw.log"],
        },
        'ignored_types': ["script", "package", "python", "debian", "HTML",
                          "RPM", "GIF", "JPEG", "PNG", "SVG", "program", "DSA",
                          "PDF", "symbolic link",
                          "executable", "shared object", "MS Windows icon"],
        'ignored_extensions': {
            '*':
            ["amd64.changes",
             ".builder", ".cfg", ".class", ".conf", ".css",
             ".deb", ".dsc",
             ".flv", ".gem",
             ".html", ".jar", ".java", ".jpg", ".js", ".json",
             ".ogg", ".ogv", ".odp", ".odt", ".ods",
             ".patch", ".pdf", ".php", ".png",
             ".ppm", "precise.tar.gz",
             ".py", ".pyc",
             ".pem", ".ring.gz", ".sh",
             ".swo", ".swp", ".ttf", ".tokudb", ".xcf",
             ".webm", "~"]
        },
        # older than 90 days is bad
        'cutoff': 90 * 86400,
        # run on this many hosts at once
        'batchsize': 20
    }
