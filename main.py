import glob
import yaml
import os
import sys
import subprocess
import tempfile
import logging
import shutil
import argparse

# CONSTANTS
cbuilder_ver = 1

class MainApp ():
    def __init__(self, args):
        self.projects = None
        self.cfg = None
        self.projects_list = []
        self.args = args
        self.load_cfg ()

    def load_cfg (self):
        fname = os.path.expanduser (args.cfg)
        f = open (fname)
        self.cfg = yaml.load (f)
        f.close ()

    def exec_cmd (self, cmd_path):
        log.debug ("Executing: %s", cmd_path)
        if self.cfg["output_stdout"] == 0:
            tmp_out = tempfile.NamedTemporaryFile (delete=True)
        else:
            tmp_out = None

        try:
            retcode = subprocess.call (cmd_path, shell=True, stdout=tmp_out, stderr=tmp_out)
            if retcode < 0:
                log.error ("Child was terminated by signal %i", retcode)
        except:
            log.error ("Execution failed: ", e)
            retcode = 1

        if self.cfg["output_stdout"] == 0:
            tmp_out.close ()

        return retcode

    def install_project (self, project):
        log.debug ("Building %s", project["name"])

        build_dir = build_dir_t + project["path"]
        log.debug ("Build dir %s", build_dir)
        project_dir = project_dir_t + project["path"]
        log.debug ("Project dir %s", project_dir)
        config_path = project_dir + "/configure"
        configure = config_path + " --prefix=" + install_dir + " " + project["flags"]
        log.debug ("Config %s", configure)
        make = "make -j5"
        make_install = make + " install"

        if any ("sudo" in s for s in project["extra"]):
            make_install = "sudo " + make_install

        shutil.rmtree (build_dir, ignore_errors=True)
        os.makedirs (build_dir , exist_ok=True)
        
        if (os.path.isdir (project_dir)):
            log.debug ("Project found, running update")
            os.chdir (project_dir)
            self.exec_cmd ("make distclean")
            self.exec_cmd (project["update"])
        else:
            log.debug ("Project not found, initializing")
            os.chdir (project_dir_t);
            self.exec_cmd (project["init"])
            os.chdir (project_dir)

        if any ("automake" in s for s in project["extra"]):
            log.debug ("Running automake");
            self.exec_cmd ("sh autogen.sh")
        
        os.chdir (build_dir)
        self.exec_cmd (configure)
        if (self.exec_cmd (make) != 0):
            log.debug ("Build failes !")

        self.exec_cmd (make_install)
    
    def install_projects (self):
        self.load_projects_list ()
        for i in self.args.projects:
            self.install_project (i)

    def load_poject (self, project_name):
        fname = config_dir + project_name + ".cfg"
        f = open (fname)
        project = yaml.load (f)
        f.close ()
        if (project["cbuilder_ver"] != cbuilder_ver):
            log.error ("Project cfg version doesn't match app version: %s", project["cbuilder_ver"])
            return

        return project

    def load_projects_list (self):
        # go through projects config files
        flist = glob.glob (self.cfg["config_dir"] + '*.cfg')
        print (self.cfg["config_dir"] )
        print (flist)
        # load project
        for fname in flist:
            f = open (fname)
            project = yaml.load (f)
            f.close ()
            self.projects_list.append (project)
        
        # bubble sort for dependencies
        for i in range (0, len (self.projects_list)):
            for j in range (0, len (self.projects_list)):
                for k in self.projects_list[j]["deps"]:
                    if (k == self.projects_list[i]["name"]):
                        tmp = self.projects_list[i]
                        self.projects_list[i] = self.projects_list[j]
                        self.projects_list[j] = tmp

    
    def print_project (self, project):
        print ("%s => %d %s", project['name'], project['cbuilder_ver'],  project['deps'])

    def list_projects (self):
        self.load_projects_list ()
        for i in self.projects_list:
            self.print_project (i)

    def sync_projects (self):
        shutil.rmtree (self.cfg["config_dir"], ignore_errors=True)
        os.makedirs (self.cfg["config_dir"])
        os.chdir (self.cfg["config_dir"])
        self.exec_cmd ("git clone git://github.com/wizzard/cbuilder.git/");
        self.exec_cmd ("mv cbuilder/scripts/* .")
        self.exec_cmd ("rm -fr cbuilder/")
        None


commands_d = {
    'install': MainApp.install_projects,
    'list': MainApp.list_projects,
    'sync': MainApp.sync_projects,
}

# main
if __name__ == '__main__':
    app_name = 'cbuilder';

    parser = argparse.ArgumentParser(prog=app_name,
    usage = '''{0} [-h] [-v] [list | info | install | sync] (project1 project2 .. )'''.format (app_name), 
    formatter_class=argparse.RawDescriptionHelpFormatter, description = '''
\tlist\t\tlist all available projects
\tinfo\t\tshow info for specified projects
\tinstall\t\tinstall specified projects
\tsync\t\tsync project config files with the remote repository'''
    )
    
    parser.add_argument("-c", "--cfg", default="~/.{0}/{0}.cfg".format (app_name), help="path to config file")
    parser.add_argument("-O", "--nodeps", action="store_true", default=False, help="do not install deps")
    parser.add_argument("-v", "--verbosity", action="count", default=0)
    parser.add_argument('projects', nargs=argparse.REMAINDER, help='list of projects')
    args = parser.parse_args()

    app = MainApp (args);

    cfg_path = os.getenv('HOME') + "/." + app_name + "/" + app_name + ".cfg"
    if not os.access(cfg_path, os.R_OK):
        print ("Can't open for reading: " + cfg_path)
        sys.exit (1)

    # setup logger
    logging.basicConfig (format='%(asctime)s %(message)s')
    log = logging.getLogger (__name__)
    if (args.verbosity > 2):
        log.setLevel (logging.DEBUG)

    # parse command line
    if (len (args.projects) < 1 or args.projects[0] not in commands_d):
        parser.print_help ()
        sys.exit (1)

    f = commands_d[args.projects[0]]
    f (app)
