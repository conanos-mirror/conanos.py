import os
import platform
import re
import sys
import tempfile
import shutil
from copy import copy
from conans import tools
from cpt.packager import ConanMultiPackager,load_cf_class


def loadScheme_(name):
    CONANOS_SCHEME_REPO = os.environ.get('CONANOS_SCHEME_REPO')
    if not CONANOS_SCHEME_REPO:
        CONANOS_SCHEME_REPO = 'https://raw.githubusercontent.com/conanos/schemes/master'
    tools.out.info('Conan build for scheme : %s'%name)
    tools.out.info('scheme repository : %s'%CONANOS_SCHEME_REPO)

    url = '%s/%s/scheme.py'%(CONANOS_SCHEME_REPO ,name)
    filename = url
    tempd = None

    if url.find(':') >1:        
        tmpd = tempfile.mkdtemp()
        filename = os.path.join(tmpd,'conanos_%s_scheme.py'%name)        
        tools.download(url,filename,overwrite=True)
    try:
        module_dir = os.path.dirname(filename)    
        module_name, ext = os.path.splitext(os.path.basename(filename))
        sys.path.insert(1, module_dir)
        module = __import__(module_name)
        assert(module.library_types)
        assert(module.options)
        assert(module.dependencies)
    except ImportError:
        tools.out.error('failed import  %s'%url)
        raise 'can not import scheme file'
    finally:        
        if tempd:
            shutil.rmtree(tmpd)
        
    return module


def _filter(pkg_name , builder):
    CONANOS_SCHEME = os.environ.get('CONANOS_SCHEME')
    if not CONANOS_SCHEME:
        tools.out.warn('conanos build without scheme.'
        'if you want to build some scheme,for example webstreamer'
        'windows > set  CONANOS_SCHEME=webstreamer'
        'linux > export CONANOS_SCHEME=webstreamer')
        
        return builder

    items = []
    scheme = loadScheme_(CONANOS_SCHEME)
    for settings, options, env_vars, build_requires, reference in builder.items:
        compiler = settings['compiler']
        if compiler == 'Visual Studio':
            compiler = 'msvc'

        ltype = scheme.library_types(pkg_name,settings)
        if ltype:
            conanfile = load_cf_class("./conanfile.py", builder.conan_api)
            if hasattr(conanfile, "options") and "shared" in conanfile.options:
                shared = options['%s:shared'%pkg_name]
                l = 'shared' if shared else 'static'
                if l == ltype or l in ltype:
                    items.append([settings, options, env_vars, build_requires])
            else:
                items.append([settings, options, env_vars, build_requires])

    builder.items = items
    return builder

def Main(name,pure_c=True):
    sch = os.environ.get("CONANOS_SCHEME")

    if not sch:
        tools.out.error('''Warning !!!!!!!!!!
        Use the conanos to build package, but you didn't set sdk name.
        Please set CONANOS_SCHEME to right name which you want build the package for.
        !!!!!!!!!!
        ''')
    else:
        tools.out.info('''
        ======================================
          package : %s
          scheme  : %s
        ======================================
        '''%(name,sch))
        scheme = loadScheme_(sch)
        if hasattr(scheme,'pre_build'):
            scheme.pre_build()


    if platform.system() == 'Windows':
        os.environ['CONAN_VISUAL_VERSIONS'] = os.environ.get('CONAN_VISUAL_VERSIONS','15')

    os.environ['CONAN_USERNAME'] = os.environ.get('CONAN_USERNAME','conanos')


    PATTERN = re.compile(r'conan(io|os)/(?P<compiler>gcc|clang|emcc)(?P<version>\d+)(-(?P<arch>\w+(-\w+)*))?')
    m = PATTERN.match(os.environ.get('CONAN_DOCKER_IMAGE',''))
    docker_entry_script = ''
    if m:
        compiler = m.group('compiler')
        version  = m.group('version')
        arch     = 'x86_64' if not m.group('arch') else m.group('arch')

        CONANOS_SCHEME      = os.environ.get("CONANOS_SCHEME")
        CONANOS_SCHEME_REPO = os.environ.get("CONANOS_SCHEME_REPO")

        docker_entry_script += "pip install conan --upgrade"
        docker_entry_script += " && pip install conan_package_tools"
        docker_entry_script += " && pip install conanos --upgrade"

        if CONANOS_SCHEME:
            docker_entry_script += " && export CONANOS_SCHEME=%s"%CONANOS_SCHEME
        if CONANOS_SCHEME_REPO:
            docker_entry_script += " && export CONANOS_SCHEME_REPO=%s"%CONANOS_SCHEME_REPO

        if os.path.exists('docker_entry_script.sh'):
            docker_entry_script +=' && /bin/bash docker_entry_script.sh %s %s %s'%(compiler,version,arch)
    
        
    builder = ConanMultiPackager(docker_entry_script=docker_entry_script)
    builder.add_common_builds(pure_c=pure_c)

    _filter(name,builder)
    
    builder.run()

def pkgconfig_adaption(conanfile,pkgconfig_folder='~pkgconfig'):

    pkgconfigd=os.path.abspath(pkgconfig_folder)
    requires = conanfile.requires
    for (name,reference) in requires.items():
        rootd = conanfile.deps_cpp_info[name].rootpath
        pcd = os.path.join(rootd,'lib/pkgconfig').replace('\\','/')
        if not os.path.isdir(pcd):
            continue
        for name in os.listdir(pcd):
            pcfile=os.path.join(pcd,name) 
            if name.endswith('.pc') and os.path.isfile(pcfile) :
                filename = os.path.join(pkgconfigd,name)
                if not os.path.isdir(pkgconfigd):
                    os.makedirs(pkgconfigd)
                shutil.copy(pcfile, filename)
                tools.replace_prefix_in_pc_file(filename,rootd.replace('\\','/'))
                tools.out.info('%s ->%s'%(name,filename))
        





def config_scheme(conanfile):
    CONANOS_SCHEME = os.environ.get('CONANOS_SCHEME')
    if not CONANOS_SCHEME:
        tools.out.warn('conanos build without scheme.'
        'if you want to build some scheme,for example webstreamer'
        'windows > set  CONANOS_SCHEME=webstreamer'
        'linux > export CONANOS_SCHEME=webstreamer')        
        return


    scheme = loadScheme_(CONANOS_SCHEME)

    name     = conanfile.name
    options  = conanfile.options
    settings = conanfile.settings
    shared = conanfile.options.shared

    # overwrite with scheme's options
    s_options = scheme.options(name,settings,shared)
    for name , val in s_options.items():
        if name in options:
            setattr(options,name, val)

    # dependencies
    deps = scheme.dependencies(name,settings)
    requires = conanfile.requires

    for (r_name,reference) in requires.items():
        if r_name in deps:
            conanfile.options[r_name].shared = deps[name]
        else:
            ltype = scheme.library_types(r_name,settings)
            ltype = ltype if isinstance(ltype,str) else ltype[0]
            assert(ltype in ['static','shared'])
            conanfile.options[r_name].shared = True if ltype == 'shared' else False

        rs_options = scheme.options(r_name,settings,shared)
        for key , val in rs_options.items():
            setattr(conanfile.options[r_name],key,val)
