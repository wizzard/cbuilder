import glob
import yaml
import os
import sys
import subprocess
import tempfile
import logging
import shutil

# CONSTANTS
app_name = "cbuilder"

# execute command, return 0 if success
def exec_cmd (cmd_path):
    if output_stdout == 0:
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

    if output_stdout == 0:
        tmp_out.close ()

    return retcode


# create sorted projects list
def create_projects_list (path, projects_list):

# go through projects config files
    flist = glob.glob (scripts_dir + '*.cfg')
    
# load project
    for fname in flist:
        f = open (fname)
        project = yaml.load (f)
        f.close ()
        projects_list.append (project)
    
# bubble sort for dependencies
    for i in range (0, len (projects_list)):
        for j in range (0, len (projects_list)):
            
            for k in projects_list[j]["deps"]:
                if (k == projects_list[i]["name"]):
                    tmp = projects_list[i]
                    projects_list[i] = projects_list[j]
                    projects_list[j] = tmp


# build project
def build_project (project):
    log.debug ("Building %s", project['path']);

# prepare configuration string
    conf_param = prefix_key + install_dir + " " + project['flags']
    build_str = projects_dir + project['path'] + config_file + conf_param

# create build dir
    log.debug ("Creating dir: %s", build_dir + project['path'])
    try:
        os.makedirs (build_dir + project['path'], exist_ok=True)
    except:
        log.error ("Failed to create dir: %s", build_dir + project['path'])
        return 1

# go to project's dir
    log.debug ("Changing dir to: %s", projects_dir + project['path']);
    try:
        os.chdir (projects_dir + project['path'])
    except:
        log.error ("Failed to chdir to: %s", build_dir + project['path'])
        return 1

# get the latest sources
    log.debug ("Checking out the sources..");
    if exec_cmd (project['pull']) == 0:
        log.debug ("Checking out the sources.. DONE");
    else:
        log.error ("Checking out the sources.. FAILED");
        return 1

# chdir to build dir
    log.debug ("Changing dir to: %s", build_dir + project['path']);
    try:
        os.chdir (build_dir + project['path'])
    except:
        log.error ("Failed to change dir to: %s", build_dir + project['path']);
        return 1

# execute autogen if requested
    if project['autogen'] == 1:
        autogen = "bash " + projects_dir + project['path'] + "/autogen.sh" 
        log.debug ("Executing %s ..", autogen);
        if exec_cmd (autogen) == 0:
            pass
        else:
            log.error ("Executing autogen.sh .. FAILED");

# exec configure
    log.debug ("Configurating project .. ");
    if exec_cmd (build_str) == 0:
        log.debug ("Confirugating project .. DONE");
    else:
        log.error ("Confirugating project .. FAILED");
        return 1

# exec make
    log.debug ("Making project .. ");
    if exec_cmd ("make " + make_flags) == 0:
        log.debug ("Making project .. DONE");
    else:
        log.error ("Making project .. FAILED");
        return 1

# exec make install
    log.debug ("Installing project .. ");
    if exec_cmd ("make install") == 0:
        log.debug ("Install project .. DONE");
    else:
        log.error ("Install project .. FAILED");
        return 1

# chdir back to origin
    log.debug ("Changing dir to: %s", cur_dir);
    try:
        os.chdir (cur_dir)
    except:
        log.error ("Failed to chdir to: %s", cur_dir);
        return 1

# clean source dir if requested
    if clean_dir:
        log.debug ("Removing dir: %s", build_dir + project['path']);
        try:
            shutil.rmtree (build_dir + project['path'], ignore_errors=True)
        except:
            log.error ("Failed to rmdir: %s", cur_dir);
            return 1

# everything is ok
    return 0


def unistall_project (project):
    log.debug ("Unistalling %s", project['path']);

# everything is ok
    return 0

# call git / svn repository init function
def init_project (project):
    log.debug ("Removing dir: %s", projects_dir + project['path']);
    try:
       shutil.rmtree (projects_dir + project['path'], ignore_errors=True)
    except:
        log.error ("Failed to remove dir: %s", projects_dir + project['path'])
        return 1
 
# go to project's dir
    log.debug ("Changing dir to: %s", projects_dir);
    try:
        os.chdir (projects_dir)
    except:
        log.error ("Failed to chdir to: %s", projects_dir);
        return 1
   
    log.debug ("Init project ..");
    if exec_cmd (project['init']) == 0:
        log.debug ("Init project .. DONE");
    else:
        log.error ("Init project .. FAILED");
        return 1

# chdir back to origin
    try:
        os.chdir (cur_dir)
    except:
        log.error ("Failed to chdir to: %s", cur_dir);
        return 1

# everything is ok    
    return 0



# print project's information
def print_project (project):
    print (project['name'], ' => ', project['deps'])


# create project list taking in account specified arguments
def create_projects_list_with_argv (path):
    requested_build = list ()
    projects_list = list ()

    create_projects_list (path, projects_list)
    if (len (sys.argv) > 2):
        for i in range (2, len (sys.argv)):
            for j in projects_list:
                if (j["name"] == sys.argv[i]):
                    requested_build.append (j)
    
    if (len (requested_build) > 0):
        return requested_build
    else:
        return projects_list

def list_projects ():
    projects_list = create_projects_list_with_argv (scripts_dir + scripts_ext)
    log.debug ("list projects:")
    for i in projects_list:
        print_project (i)


def init_projects ():
    projects_list = create_projects_list_with_argv (scripts_dir + scripts_ext)

    log.debug ("Initializing projects:")

    for i in projects_list:
        print_project (i)
        init_project (i)

def build_projects ():
    projects_list = create_projects_list_with_argv (scripts_dir + scripts_ext)

    log.debug ("Building projects:")

    for i in projects_list:
        print_project (i)
    
    for i in projects_list:
        res = build_project (i)
        if res == 1:
            log.error ("Failed to build project, stopping")
            return 1

def unistall_projects ():
    projects_list = create_projects_list_with_argv (scripts_dir + scripts_ext)

    log.debug ("Unistalling projects:")

    for i in projects_list:
        print_project (i)

#TODO: countdown    
    for i in projects_list:
        res = unistall_project (i)
        if res == 1:
            log.error ("Failed to unistall project, stopping")
            return 1


def show_help ():
    print ("Usage: ")
    print ("\t", sys.argv[0], " [help | list | init | build | unistall] (project1 project2 .. )")
    print ("\t", "list - list all available projects")
    print ("\t", "init - init git / svn repositories for specified projects")
    print ("\t", "build - build all or only specified projects")
    print ("\t", "unistall - remove specified projects files")



commands_d = {
    'help': show_help,
    'list': list_projects,
    'init': init_projects,
    'build': build_projects,
    'unistall': unistall_projects,
}


# main
if __name__ == '__main__':
    
    cfg_path = os.getenv('HOME') + "/." + app_name + "/" + app_name + ".cfg"
    if not os.access(cfg_path, os.R_OK):
        print ("Can't open for reading: " + cfg_path)
        sys.exit (1)

# setup logger
    logging.basicConfig (format='%(asctime)s %(message)s')
    log = logging.getLogger (__name__)
    log.setLevel (logging.DEBUG)

# parse command line
    if (len (sys.argv) < 2 or sys.argv[1] not in commands_d):
        show_help ()
        sys.exit (1)
    
    f = commands_d[sys.argv[1]]
    f ()
