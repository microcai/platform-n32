import sys
from os.path import isdir, join
from os import listdir
import re
import difflib

from SCons.Script import DefaultEnvironment

env = DefaultEnvironment()
platform = env.PioPlatform()
board = env.BoardConfig()

FRAMEWORK_DIR = platform.get_package_dir("framework-N32sdk")
assert isdir(FRAMEWORK_DIR)

bsp_name = board.get('build.core', '').upper()  # e.g. N32G430

driver_dir = join(FRAMEWORK_DIR, bsp_name, 'firmware','Driver')
cmsis_dir = join(FRAMEWORK_DIR, bsp_name, 'firmware', 'CMSIS')

machine_flags = [
    '-mthumb',
    '-mcpu={}'.format(board.get('build.cpu')),
]

env.Append(
    ASFLAGS=machine_flags,
    ASPPFLAGS=['-x', 'assembler-with-cpp'],

    CCFLAGS=machine_flags + [
        "-Os",  # optimize for size
        "-ffunction-sections",  # place each function in its own section
        "-fdata-sections",
        "-Wall",
        "-nostdlib",
    ],

    CXXFLAGS=[
        "-fno-rtti",
        "-fno-exceptions",
        "-fno-threadsafe-statics",
        '-Wno-register',
    ],

    CPPDEFINES=[
        bsp_name,
    ],

    # includes
    CPPPATH=[
        join(cmsis_dir, 'core'),
        join(cmsis_dir, 'device'),
        join(driver_dir, 'inc'),
        env.subst("${PROJECT_INCLUDE_DIR}"),  # place for n32g430_conf.h
    ],
    LINKFLAGS=machine_flags + [
        "-Os",
        "-Wl,--gc-sections,--relax",
        "--specs=nano.specs",
        "--specs=nosys.specs",
        "-mthumb",
        "-mcpu=cortex-m4",
        "-mfpu=fpv4-sp-d16",
        "-mfloat-abi=hard",
        "-static",
        "-Wl,--check-sections",
        "-Wl,--unresolved-symbols=report-all",
        "-Wl,--warn-common",
        "-Wl,-Map,%s/linkmap.map" % env.get("BUILD_DIR")
    ],

    LIBS=["c", "m"],

)

# env.Append(
#     ASFLAGS=env.get("CCFLAGS", [])[:]
# )

def parse_ld_num(v: str):
    if v.endswith('K'):
        return int(v[:-1]) * 1024
    elif v.endswith('M'):
        return int(v[:-1]) * 1024 * 1024
    else:
        return int(v, 0)


def get_linker_sizes(ld_file: str):
    """Very hacky way to read flash/ram size from ld file. """
    try:
        with open(ld_file, 'r', encoding='utf-8') as f:
            all = f.read()
            flash = re.findall(r'FLASH.*ORIGIN\s*=\s*(\w*),\s*LENGTH\s*=\s*(\w*)', all)[0]
            ram = re.findall(r'RAM.*ORIGIN\s*=\s*(\w*),\s*LENGTH\s*=\s*(\w*)', all)[0]
            return parse_ld_num(flash[1]), parse_ld_num(ram[1])
    except IndexError:
        return None
    return None


ldscript = board.get('build.ldscript', '')
if not ldscript:
    raise RuntimeError('Board has no ldscript!')
ldscript = join(cmsis_dir, 'device', ldscript)
env.Replace(LDSCRIPT_PATH=ldscript)

sizes = get_linker_sizes(ldscript)
board.update("upload.maximum_size", str(sizes[0]))
board.update("upload.maximum_ram_size", str(sizes[1]))

env.BuildSources(
    join('$BUILD_DIR', 'Driver'),
    join(driver_dir, 'src'),
)

libs = []


def select_best_file(path, filemask, mcu):
    presize_file = filemask.format(mcu)  # e.g. system_.c
    filemask = filemask.format('.*')
    files = [p for p in listdir(path) if re.match(filemask, p)]

    for f in files:
        if re.match(f.replace('x', '.'), presize_file):
            return f
    return None


cmsis_src_dir = join(cmsis_dir, 'device')
sys_file = select_best_file(cmsis_src_dir, 'system_{}.c', bsp_name.lower())
libs.append(
    env.BuildLibrary(
        join("$BUILD_DIR", "FrameworkCMSISDevice"),
        cmsis_src_dir,
        src_filter=[
            '-<*>',
            '+<startup/startup_{}_gcc.s>'.format(bsp_name.lower()),
            '+<{}>'.format(sys_file),
        ],
    )
)

env.Prepend(LIBS=libs)
