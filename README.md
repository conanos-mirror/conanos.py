# conanos.py
conanos build utils


# Features

## Build SDK by scheme


SDK is a set of libs, and configure of the lib is specified. for example SDK include libA libB  libC. libA and libB is shared and libC is static. if you build such a combination, you have to do some hard code in 'conanfile.py', to simplify such work we introduce the scheme in conanos.

after you installed conanos, you have to set 2 enviroment vars to be used for conan build (for the  scheme ) .

 * CONANOS_SCHEME 
   
   the name of the scheme.

 * CONANOS_SCHEME_REPO

   the scheme file where placed in.
   If set, the conanos will download/copy frome ${CONANOS_SCHEME_REPO}/${CONANOS_SCHEME}/scheme.py. Otherwise conanos will download from default site https://raw.githubusercontent.com/conanos/schemes/master

here is a exaple in windows
``` dos
set CONANOS_SCHEME=webstreamer
set CONANOS_SCHEME_REPO=path_or_url_place_the_scheme
conan create . conanos/stable
```

### how to use such feature?
if you build a SDK's lib, you only need to add config_scheme in requriements

```python
class LibXXXX(ConanFile):
    .....

    def requirements(self):
        scheme_config(self)
```

## extension conan_package_tools build for conanos

for CI build, conan had provide conan-package-tool. in our webstreamer project, every package almose has same pattern to do on build.

so we wrapper a function Main to simply, in you build.py you only need as below, you have to replace the 'zlib' as your package's name.

```python
#!/usr/bin/env python
from conanos.build import Main

if __name__ == "__main__":    
    Main('zlib',pure_c=True)
```

then you can run

```sh
export CONANOS_SCHEME=webstreamer
export CONANOS_SCHEME_REPO=path_or_url_place_the_scheme
    ......
python bui.d.py
```

### for docker

In the conanos.build.Main, we also wrap the docker script runner. 

For example, if you want to install ninja for build in docker, you can write theses commands in 'docker_entry_script.sh' file under same folder of build.py.

please ref project https://github.com/conanos/libffi

in docker, conanos auto inatall conanos python package, so you do not need add conanos installation command in  docker_entry_script.sh.


## package config file (.pc)

in conanos build, many libs need find include/lib path from pkg-config file,for example zlib.pc. 

We make the rule for .pc file

1. all pkg-config file (.pc) put in lib/pkgconfig
2. all .pc file directory var must be a relative path to ${prefix}
3. the prefix point to root directory of the package
    
    ```sh
    # exmpale of pc adhere to the rules
    prefix=D:/github.com/conanos/zlib/package
    exec_prefix=${prefix}/bin
    libdir=${prefix}/lib
    sharedlibdir=${prefix}/lib
    includedir=${prefix}/include
        ...... 
    ```
with above 3 rules, we wrapped function pkgconfig_adaption to find pc file easily.


in pkgconfig_adaption will search all depend libs .pc and reaplace ther 'prefix' to right path. all the found and modified pc will be put in ~pkgconfig by default.

the pkgconfig_adaption should be called in build

```python
class LibXXX(ConanFile):

    .....
    def build(self):
        pkgconfig_adaption(self, path_put_the_adpated_pc_file)
        .......

```

**Lesson Learned**
in MSVC build, since we use the pkg-config in msys2 (msys2_installer/20161025@bincrafters/stable).
even we set directory to PKG_CONFIG_PATH to the *path_put_the_adpated_pc_file*, the package search still failed, normally, this cause by wrong format path, may be you set a do path (i.e d:/1/2/3),but it could not recognized by msys2(bash), so you have to change it to proper one.

in conanfile.py, you'd add following code
```python

class LibXXX(ConanFile):

    def build_requirements(self):
        if platform.system() == "Windows":
            self.build_requires("msys2_installer/20161025@bincrafters/stable")

    def build(self):
        
        pkgconfigdir=os.path.abspath('~pkgconfig')    # put package config file into 
        pkgconfig_adaption(self,pkgconfigdir)         # do the adaption
        pkg_config_paths=[
            tools.unix_path(pkgconfigdir,tools.MSYS2) # we change to msys2 format pat
        ]

        meson = Meson(self)
        meson.configure(pkg_config_paths=pkg_config_paths ) 
        meson.build()
```