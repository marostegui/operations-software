import os
MYDIR=os.path.dirname(os.path.realpath(__file__))
PARENT=os.path.realpath(os.path.join(MYDIR,'..'))
BASEDIR = os.environ.get('PUPPET_COMPILER_BASEDIR', PARENT)
get_path = lambda x: os.path.join(BASEDIR, x)

COMPILE_SCRIPT = get_path('shell/compile')
FETCH_CHANGE = get_path('shell/prepare_change')
HELPER_SCRIPT = get_path('shell/helper')
DIFF_SCRIPT = get_path('shell/differ')
NODE_DIR = get_path('external/var/yaml/node')
PUPPET_VERSIONS = [('2.7', 'production'), ('3', 'production')]

BASE_OUTPUT_DIR = get_path('output')
# Jenkins support
OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, os.environ.get('BUILD_NUMBER', ''))
COMPILE_OUTPUT_DIR = os.path.join(OUTPUT_DIR, 'compiled')
DIFF_DIR = os.path.join(OUTPUT_DIR, 'diff')
HTML_DIR = os.path.join(OUTPUT_DIR, 'html')
