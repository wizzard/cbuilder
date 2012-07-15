#!/usr/bin/python3

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
version_keys = ("cbuilder_ver", "name", "path", "flags", "init", "update", "deps", "extra")

class TreeNode:
    def __init__(self, name, obj, level = 0):
        self.name = name
        self.obj = obj
        self.parent = None
        self.children = []
        self.level = level

class Tree:
    def __init__(self):
        self.nodes = []
        self.root = TreeNode ("root", None, 0)
        self.nodes.append (self.root)

    def add (self, name, obj = None, parent_name = None):
        node = TreeNode (name, obj)
        if parent_name == None:
            parent_name = "root"

        for i in self.nodes:
            if i.name == parent_name:
                i.children.append (node)
                node.parent = i
                node.level = i.level + 1

        self.nodes.append (node)

    def print (self, node=None):
        if not node:
            node = self.nodes[0]
        if node.level > 0:
            print ("\t"*node.level, "{0}".format (node.name))
        for i in node.children:
            self.print (i)
    
    def breadth_first (self, root):
        if not root:
            return
        old = []
        new = []
        old.append (root)
        while old:
            for n in old:
                print (n.name);
                new += n.children
            old = new
            new = []

class MainApp ():
    def __init__(self, args):
        self.projects = None
        self.cfg = None
        self.projects_list = []
        self.args = args
        self.load_cfg ()
        self.project_tree = Tree ()

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

        build_dir = self.cfg["build_dir_t"] + project["path"]
        log.debug ("Build dir %s", build_dir)
        project_dir = self.cfg["project_dir_t"] + project["path"]
        log.debug ("Project dir %s", project_dir)
        config_path = project_dir + "/configure"
        configure = config_path + " --prefix=" + self.cfg["install_dir"] + " " + project["flags"]
        log.debug ("Config %s", configure)
        make = "make -j5"
        make_install = make + " install"
        ldconfig = "/sbin/ldconfig -N -n " + self.cfg["install_dir"] + "lib"

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
            os.makedirs (project_dir , exist_ok=True)
            os.chdir (self.cfg["project_dir_t"]);
            self.exec_cmd (project["init"])
            os.chdir (project_dir)

        if any ("automake" in s for s in project["extra"]):
            log.debug ("Running automake");
            self.exec_cmd ("sh autogen.sh")
        
        os.chdir (build_dir)
        log.debug ("Executing config script: %s", configure)
        self.exec_cmd (configure)
        log.debug ("Executing make: %s", make)
        if (self.exec_cmd (make) != 0):
            log.debug ("Build failes !")

        log.debug ("Installing: %s", make_install)
        self.exec_cmd (make_install)

        log.debug ("Executing ldconfig: %s", ldconfig)
        self.exec_cmd (ldconfig)

    def install_project_list (self, project_list):
        for i in project_list:
            project = self.get_project (i)
            if not project:
                log.error ("Project %s not found !", i)
                continue
            
            # install deps
            if not self.args.nodeps:
                self.install_project_list (project["deps"])

            self.install_project (project)
   
    def install_projects (self):
        if not self.load_projects_list ():
            return

        self.args.projects.pop (0)
        self.install_project_list (self.args.projects)

    
    def get_project (self, project_name):
        for i in self.projects_list:
            if (i["name"] == project_name):
                return i
        return None
        
    def load_poject (self, project_name):
        f = open (project_name)
        project = yaml.load (f)
        f.close ()

        for i in version_keys:
            if not i in project:
                log.error ("Key not found: %s", i)
                return None
            
        if (project["cbuilder_ver"] != cbuilder_ver):
            log.error ("Project cfg version doesn't match app version: %s", project["cbuilder_ver"])
            return None

        return project

    def load_projects_list (self):
        # go through projects config files
        flist = glob.glob (self.cfg["config_dir"] + '*.cfg')
        # load project
        for fname in flist:
            project = self.load_poject (fname)
            if (project == None):
                return
            self.projects_list.append (project)

        self.project_tree.add (project["name"], project, 
        
        # bubble sort for dependencies
        for i in range (0, len (self.projects_list)):
            for j in range (0, len (self.projects_list)):
                for k in self.projects_list[j]["deps"]:
                    if (k == self.projects_list[i]["name"]):
                        tmp = self.projects_list[i]
                        self.projects_list[i] = self.projects_list[j]
                        self.projects_list[j] = tmp

        return True

    
    def print_project (self, project):
        print (project['name'], ' => ver:', project['cbuilder_ver'], ' deps:', project['deps'])

    def list_projects (self):
        if not self.load_projects_list ():
            return

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
    tree = Tree ()
    tree.add ("test1")
    tree.add ("test11", parent_name="test1")
    tree.add ("test12", parent_name="test1")
    tree.add ("test13", parent_name="test1")
    tree.add ("test2")
    tree.add ("test3")
    tree.add ("test4")
    tree.add ("test41", parent_name="test4")
    tree.add ("test42", parent_name="test4")
    tree.add ("test421", parent_name="test42")
    tree.add ("test422", parent_name="test42")
    tree.add ("test43", parent_name="test4")
    tree.add ("test5")
    tree.print ()

    tree.breadth_first (tree.root)

    sys.exit (1)

    

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
