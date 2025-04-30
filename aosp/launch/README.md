# 系统启动


<img src="aosp/launch/resources/launch_1.png"/>

Android 系统启动本身就是一个 Linux 系统启动的标准流程。

## Boot ROM 加载并执行

类似于我们 PC 启动会进入 bios 一样，手机启动也会由硬件控制上电执行 Boot ROM 的逻辑，在 Boot ROM 中，会进行一些硬件检测任务，随后加载 BootLoader 到内存中，并跳转到 BootLoader 的逻辑。

## BootLoader 执行

BootLoader 会进一步的进行设备的检测，随后加载内核到内存中，并跳转到内核逻辑执行。


## Kernel 执行

和 Linux kernel 一样，内核都是多阶段加载的方式来执行，内核最初的部分会初始化中断向量，随后初始化 c 环境，并创建好第一个进程 Swapper。这个进程是所有 Android 进程的祖先。

## Swapper 进程

Swapper 进程是一个内核进程，其会执行如下操作：
1. 初始化内存管理 、文件系统 、进程管理逻辑，这代表整个内核的功能初始化完毕。
2. 加载硬件驱动。
3. 创建其余的内核进程。
4. 创建第一个用户空间进程 init 进程。

## init 进程

init 进程是所有用户空间进程的祖先。init 进程除了做一些初始化操作外，还会创建一系列的 native 守护进程，例如 binder 中的 service-manager，abdb 进程用于 adb 调试通信。还有一个重要的进程 zygote.

## Zygote 进程

Zygote 进程是所有 andoroid 应用的父进程。所有的 android 应用都由其 fork 出来。在 zygote初始化后，其会做如下操作：

1. 加载 java 库资源以及 android 资源，为的是后面 fork 出来应用，可以复用，提升 app 启动速度。
2. 初始化系统服务。
3. 监听应用创建信息。


## SystemServer

SystemServer 的主要作用是启动各种系统服务，比如 ActivityManagerService, PackageManagerService, WindowManagerService 等服务。在我们通常开发应用的时候会使用到各种系统服务，都是通过 SystemServer 来进行服务获取以及调用。

在所有的服务启动完成后，SystemServer 会调用每个服务的 `service.systemReady(…)` 来通知对应的服务。

其中有一个关键的点，ActivityManagerService 收到 systemReady 调用后，会通过一个 Intent 来启动 launcher，最终整个完成整个系统启动过程。

# init 进程启动详解

## 内核触发

内核会在 `init/main.c` 中尝试寻找 init 的可执行文件，并进行触发。

```c
static int __ref kernel_init(void *unused)
{
    // ......
    const char * ramdisk_execute_command = "/init";
	if (ramdisk_execute_command) {
		ret = run_init_process(ramdisk_execute_command);
		if (!ret)
			return 0;
		pr_err("Failed to execute %s (error %d)\n",
		       ramdisk_execute_command, ret);
	}
	/*
	 * We try each of these until one succeeds.
	 *
	 * The Bourne shell can be used instead of init if we are
	 * trying to recover a really broken machine.
	 */
	if (execute_command) {
		ret = run_init_process(execute_command);
		if (!ret)
			return 0;
		panic("Requested init %s failed (error %d).",
		      execute_command, ret);
	}
	if (!try_to_run_init_process("/sbin/init") ||
	    !try_to_run_init_process("/etc/init") ||
	    !try_to_run_init_process("/bin/init") ||
	    !try_to_run_init_process("/bin/sh"))
		return 0;

	panic("No working init found.  Try passing init= option to kernel. "
	      "See Linux Documentation/admin-guide/init.rst for guidance.");
}
```

## init 进程

下面展示了 init 进程的主函数

```c
int main(int argc, char** argv) {
#if __has_feature(address_sanitizer)
    __asan_set_error_report_callback(AsanReportCallback);
#endif

    if (!strcmp(basename(argv[0]), "ueventd")) {
        return ueventd_main(argc, argv);
    }

    if (argc > 1) {
        if (!strcmp(argv[1], "subcontext")) {
            android::base::InitLogging(argv, &android::base::KernelLogger);
            const BuiltinFunctionMap function_map;

            return SubcontextMain(argc, argv, &function_map);
        }

        if (!strcmp(argv[1], "selinux_setup")) {
            return SetupSelinux(argv);
        }

        if (!strcmp(argv[1], "second_stage")) {
            return SecondStageMain(argc, argv);
        }
    }

    return FirstStageMain(argc, argv);
}
```

### 阶段1: FirstStageMain

> system/core/init/first_stage_init.cpp

`FirstStageMain` 的主要任务是挂载虚拟文件系统，一共后面的流程使用。

#### `InstallRebootSignalHandlers`

1. 这个函数主要是对进程的基本信号处理方式进行初始化。
2. 对于 init 进程来说，如果收到某些错误信号，就执行 InitFatalReboot, 重启系统。
3. 对于其他进程，直接调用 exit 退出进程即可。

```c
void InstallRebootSignalHandlers() {
    // Instead of panic'ing the kernel as is the default behavior when init crashes,
    // we prefer to reboot to bootloader on development builds, as this will prevent
    // boot looping bad configurations and allow both developers and test farms to easily
    // recover.
    struct sigaction action;
    memset(&action, 0, sizeof(action));
    sigfillset(&action.sa_mask);
    action.sa_handler = [](int signal) {
        // These signal handlers are also caught for processes forked from init, however we do not
        // want them to trigger reboot, so we directly call _exit() for children processes here.
        if (getpid() != 1) {
            _exit(signal);
        }

        // Calling DoReboot() or LOG(FATAL) is not a good option as this is a signal handler.
        // RebootSystem uses syscall() which isn't actually async-signal-safe, but our only option
        // and probably good enough given this is already an error case and only enabled for
        // development builds.
        InitFatalReboot();
    };
    action.sa_flags = SA_RESTART;
    sigaction(SIGABRT, &action, nullptr);
    sigaction(SIGBUS, &action, nullptr);
    sigaction(SIGFPE, &action, nullptr);
    sigaction(SIGILL, &action, nullptr);
    sigaction(SIGSEGV, &action, nullptr);
#if defined(SIGSTKFLT)
    sigaction(SIGSTKFLT, &action, nullptr);
#endif
    sigaction(SIGSYS, &action, nullptr);
    sigaction(SIGTRAP, &action, nullptr);
}
```

#### `CheckCall(XXX)`

第二步是进行一些系统操作的执行，主要的内容是进行一些环境的设置以及文件系统的准备。

挂载的文件系统主要有四类：
- tmpfs: 一种虚拟内存文件系统，它会将所有的文件存储在内存中。由于 tmpfs 是驻留在 RAM 的，因此它的内容是不持久的。断电后，tmpfs 的内容就消失了，这也是被称作 tmpfs 的根本原因。
- devpts: 为伪终端提供了一个标准接口，它的标准挂接点是 /dev/pts。只要 pty(pseudo-tty, 虚拟终端)的主复合设备 /dev/ptmx 被打开，就会在 /dev/pts 下动态的创建一个新的 pty 设备文件。
- proc: 也是一个虚拟文件系统，它可以看作是内核内部数据结构的接口，通过它我们可以获得系统的信息，同时也能够在运行时修改特定的内核参数。
- sysfs: 与 proc 文件系统类似，也是一个不占有任何磁盘空间的虚拟文件系统。它通常被挂接在 /sys 目录下。

```c
    CHECKCALL(clearenv());
    CHECKCALL(setenv("PATH", _PATH_DEFPATH, 1));
    // Get the basic filesystem setup we need put together in the initramdisk
    // on / and then we'll let the rc file figure out the rest.
    CHECKCALL(mount("tmpfs", "/dev", "tmpfs", MS_NOSUID, "mode=0755"));
    CHECKCALL(mkdir("/dev/pts", 0755));
    CHECKCALL(mkdir("/dev/socket", 0755));
    CHECKCALL(mount("devpts", "/dev/pts", "devpts", 0, NULL));
#define MAKE_STR(x) __STRING(x)
    CHECKCALL(mount("proc", "/proc", "proc", 0, "hidepid=2,gid=" MAKE_STR(AID_READPROC)));
#undef MAKE_STR
    // Don't expose the raw commandline to unprivileged processes.
    CHECKCALL(chmod("/proc/cmdline", 0440));
    gid_t groups[] = {AID_READPROC};
    CHECKCALL(setgroups(arraysize(groups), groups));
    CHECKCALL(mount("sysfs", "/sys", "sysfs", 0, NULL));
    CHECKCALL(mount("selinuxfs", "/sys/fs/selinux", "selinuxfs", 0, NULL));

    CHECKCALL(mknod("/dev/kmsg", S_IFCHR | 0600, makedev(1, 11)));

    if constexpr (WORLD_WRITABLE_KMSG) {
        CHECKCALL(mknod("/dev/kmsg_debug", S_IFCHR | 0622, makedev(1, 11)));
    }
```

#### 日志重定向

在 init 进程初始化的过程中，logd 进程是还没有初始化的，这部分的日志为了后续也可以通过 logd 看到，所以需要做重定向。

#### `DoFirstStageMount`

装载 `/system` `/vendor` `/odm` 分区。

#### 进入下一阶段

exec 重新运行 init 进程，进入下一阶段 `selinux_setup`

```c
    // .....

    const char* path = "/system/bin/init";
    const char* args[] = {path, "selinux_setup", nullptr};
    execv(path, const_cast<char**>(args));

    // execv() only returns if an error happened, in which case we
    // panic and never fall through this conditional.
    PLOG(FATAL) << "execv(\"" << path << "\") failed";

    return 1;
```

### 阶段2: SetupSelinux

SetupSelinux 这个管线中主要流程如下：

1. 先调用 `InitKernelLogging(argv)` 初始化内核日志，再调用 `InstallRebootSignalHandlers()` 注册需要处理的信号，这个和第一阶段是一样的
> 为什么还需要重新注册呢？ 因为 `exec` 函数会把整个用户空间进行替换，所以原来的 `handler` 都不存在了，所以也不会继承。
2. 接着调用 `SelinuxSetupKernelLogging()` 将 `selinux` 日志重定向到内核
3. 接着调用 `SelinuxInitialize` 加载 `selinux_policy` 策略文件，设置默认 `selinux` 模式

```c
void SelinuxInitialize() {
    Timer t;

    LOG(INFO) << "Loading SELinux policy";
    // 加载 selinux_policy 策略文件
    if (!LoadPolicy()) {
        LOG(FATAL) << "Unable to load SELinux policy";
    }

    bool kernel_enforcing = (security_getenforce() == 1);
    bool is_enforcing = IsEnforcing();
    if (kernel_enforcing != is_enforcing) {
        // 设置默认 selinux 模式
        if (security_setenforce(is_enforcing)) { 
            PLOG(FATAL) << "security_setenforce(%s) failed" << (is_enforcing ? "true" : "false");
        }
    }

    if (auto result = WriteFile("/sys/fs/selinux/checkreqprot", "0"); !result) {
        LOG(FATAL) << "Unable to write to /sys/fs/selinux/checkreqprot: " << result.error();
    }

    // init's first stage can't set properties, so pass the time to the second stage.
    setenv("INIT_SELINUX_TOOK", std::to_string(t.duration().count()).c_str(), 1);
}
```

4. 最后调用 `selinux_android_restorecon` 来设置 `init` 的安全上下问，接着通过 `execv` 跳转到第二阶段

```c
const char* path = "/system/bin/init";
const char* args[] = {path, "second_stage", nullptr};
execv(path, const_cast<char**>(args));
```

### 阶段3：second_stage

```c
int SecondStageMain(int argc, char** argv) {
    // 依然需要注册信号处理函数
    if (REBOOT_BOOTLOADER_ON_PANIC) {
        InstallRebootSignalHandlers();
    }
    //...

    // 重定向日志
    SetStdioToDevNull(argv);
    InitKernelLogging(argv);
    LOG(INFO) << "init second stage started!";
    SelinuxSetupKernelLogging();
    // Update $PATH in the case the second stage init is newer than first stage init, where it is
    // first set.
    //...
    // 开启属性服务
    StartPropertyService(&property_fd);
    //...
    // 加载 init.rc 文件
    LoadBootScripts(am, sm);
}
```

### 阶段4：加载 `init.rc` 文件

#### `init.rc` 文件格式

`init.rc` 文件类似 yml 文件，以块为单位，块分为动作块和服务。

- 动作：以关键字 on 开头，表示在某个时候执行的一组命令。

```yaml
on  <trigger>         # 触发条件
    <command>         # 执行命令
    <command1>        # 可以执行多个命令
```

- 服务：以关键在 service 开头，表示启动某个进程。

```yaml
service <name> <pathname> [ <argument> ]*
    <option>
    <option>
```

#### `init.rc` 文件解析

LoadBootScripts 会解析所有的 `*.rc` 文件，并将解析出来的 action 和 service 存储在 ActionManager 和 ServiceList 中。

```c
static void LoadBootScripts(ActionManager& action_manager, ServiceList& service_list) {
    Parser parser = CreateParser(action_manager, service_list);
    std::string bootscript = GetProperty("ro.boot.init_rc", "");
    if (bootscript.empty()) {
        parser.ParseConfig("/system/etc/init/hw/init.rc");
        if (!parser.ParseConfig("/system/etc/init")) {
            late_import_paths.emplace_back("/system/etc/init");
        }
        // late_import is available only in Q and earlier release. As we don't
        // have system_ext in those versions, skip late_import for system_ext.
        parser.ParseConfig("/system_ext/etc/init");
        if (!parser.ParseConfig("/vendor/etc/init")) {
            late_import_paths.emplace_back("/vendor/etc/init");
        }
        if (!parser.ParseConfig("/odm/etc/init")) {
            late_import_paths.emplace_back("/odm/etc/init");
        }
        if (!parser.ParseConfig("/product/etc/init")) {
            late_import_paths.emplace_back("/product/etc/init");
        }
    } else {
        parser.ParseConfig(bootscript);
    }
}
```

在分析完成后，会按照顺序以 trigger 为单位进行触发，等一个 trigger 中的 action 按照顺序执行完成后，再执行下一个 trigger。

# zygote 进程启动分析

<img src="aosp/launch/resources/launch_2.png" style="width:30%"/>

1. init.rc 中定义了一个 action late-init, 其会在 init 进程初始化完成后被触发。
2. late-init 会进一步触发 zygote-start action。
3. zygote-start 会按序触发 zygote 和 zygote_secondary 两个服务。
4. zygote 和 zygote_secondary 服务本质是调用 app_process 命令行工具。
5. app_process 接收不同的参数来初始化 zygote 进程。

## app_process 用法

```bash
app_process [java-options] cmd-dir start-class-name [options]

/system/bin/app_process32 -Xzygote /system/bin --zygote --start-system-server --socket-name=zygote
```

- `-Xzygote` 属于 java-options，这些参数最终会传递给 Java 虚拟机。并且参数必须以 - 开头，一旦遇到非 - 或者 --，表示 ```java-options``` 结束。
- `/system/bin` 属于程序运行目录。
- `--xx` 开头的部分都属于 `options`。这些参数都以符号--开头。参数 --zygote 表示要启动 Zygote 进程，--start-system-server 表示要启动 SystemServer，--socket-name=zygote 用于指定 Zygote 中 socket 服务的名字。

## app_process 流程

1. 初始化 AppRuntime, AppRuntime 主要用来创建和初始化虚拟机。
2. 解析 java options, 并将其存储在 AppRuntime 中。
3. 启动对应的 java 类。

```cpp
int main(int argc, char* const argv[])
{
    //...
    // 初始化 Runtime
    AppRuntime runtime(argv[0], computeArgBlockSize(argc, argv));
    // Process command line arguments
    // ignore argv[0]
    argc--;
    argv++;
    //...
    // 解析 java options
    while (i < argc) {
        const char* arg = argv[i++];
        if (strcmp(arg, "--zygote") == 0) {
        //...
        } else if (strncmp(arg, "--", 2) != 0) {
            className = arg;
            break;
        } else {
            --i;
            break;
        }
    }
    // 在 runtime 中启动对应的 java 类
    if (zygote) {
        runtime.start("com.android.internal.os.ZygoteInit", args, zygote);
    } else if (!className.empty()) {
        runtime.start("com.android.internal.os.RuntimeInit", args, zygote);
    } else {
        fprintf(stderr, "Error: no class name or --zygote supplied.\n");
        app_usage();
        LOG_ALWAYS_FATAL("app_process: no class name or --zygote supplied.");
    }
}
```

## runtime.start 流程

AppRuntime 提供了一个执行 java 字节码的环境。

### AppRuntime 初始化

AppRuntime 初始化的时候，会初始化 skia 图形系统，并把自己绑定到 global static 变量。

```cpp
static AndroidRuntime* gCurRuntime = NULL;

AndroidRuntime::AndroidRuntime(char* argBlockStart, const size_t argBlockLength) :
        mExitWithoutCleanup(false),
        mArgBlockStart(argBlockStart),
        mArgBlockLength(argBlockLength)
{
    SkGraphics::Init();
    mOptions.setCapacity(20);
    assert(gCurRuntime == NULL);
    gCurRuntime = this;
}

class AppRuntime : public AndroidRuntime
{
public:
    AppRuntime(char* argBlockStart, const size_t argBlockLength)
        : AndroidRuntime(argBlockStart, argBlockLength)
        , mClass(NULL)
    {
    }

    //......

    String8 mClassName;
    Vector<String8> mArgs;
    jclass mClass;
};
```

### AppRuntime.start

1. 环境相关初始化

2. 注册 jni

```c
static int register_jni_procs(const RegJNIRec array[], size_t count, JNIEnv* env)
{
    for (size_t i = 0; i < count; i++) {
        if (array[i].mProc(env) < 0) {
#ifndef NDEBUG
            ALOGD("----------!!! %s failed to load\n", array[i].mName);
#endif
            return -1;
        }
    }
    return 0;
}
static const RegJNIRec gRegJNI[] = {
    REG_JNI(register_com_android_internal_os_RuntimeInit),
    REG_JNI(register_com_android_internal_os_ZygoteInit_nativeZygoteInit),
    REG_JNI(register_android_os_SystemClock),
    REG_JNI(register_android_util_EventLog),
    REG_JNI(register_android_util_Log),
    REG_JNI(register_android_util_MemoryIntArray),
    REG_JNI(register_android_util_PathParser),
    REG_JNI(register_android_util_StatsLog),
    REG_JNI(register_android_util_StatsLogInternal),
    REG_JNI(register_android_app_admin_SecurityLog),
    REG_JNI(register_android_content_AssetManager),
    REG_JNI(register_android_content_StringBlock),
    REG_JNI(register_android_content_XmlBlock),
    REG_JNI(register_android_content_res_ApkAssets),
    REG_JNI(register_android_text_AndroidCharacter),
    REG_JNI(register_android_text_Hyphenator),
    REG_JNI(register_android_view_InputDevice),
    REG_JNI(register_android_view_KeyCharacterMap),
    REG_JNI(register_android_os_Process),
    REG_JNI(register_android_os_SystemProperties),
    REG_JNI(register_android_os_Binder),
    REG_JNI(register_android_os_Parcel),
    REG_JNI(register_android_os_HidlSupport),
    REG_JNI(register_android_os_HwBinder),
    REG_JNI(register_android_os_HwBlob),
    REG_JNI(register_android_os_HwParcel),
    REG_JNI(register_android_os_HwRemoteBinder),
    REG_JNI(register_android_os_NativeHandle),
    // ...... 省略大部分
};
```

3. 通过 jni 启动 `com.android.internal.os.ZygoteInit`

- 获取 `ZygoteInit` 类中的 `main` 方法
- 调用 `main` 方法

```c
// className = com.android.internal.os.ZygoteInit
char* slashClassName = toSlashClassName(className != NULL ? className : "");
jclass startClass = env->FindClass(slashClassName);
if (startClass == NULL) {
    ALOGE("JavaVM unable to locate class '%s'\n", slashClassName);
    /* keep going */
} else {
    jmethodID startMeth = env->GetStaticMethodID(startClass, "main",
        "([Ljava/lang/String;)V");
    if (startMeth == NULL) {
        ALOGE("JavaVM unable to find main() in '%s'\n", className);
        /* keep going */
    } else {
        env->CallStaticVoidMethod(startClass, startMeth, strArray);
        //...
    }
//...
}
```

### ZygoteInit.main 

1. 解析参数，初始化一些数据。
2. 初始化 zygoteServer 对象，调用 forkSystemServer 创建 SystemServer 进程。

> SystemServer 进程是一个非常重要的进程，几乎所有 java 层的binder 服务都运行在这个进程中。

forkSystemServer 会通过 jni 调用到 c 中的 fork 函数来创建新的进程。

forkSystemServer 返回后，如果不是 null ，就代表是 SystemServer 进程，这个进程通过 run 方法来执行自己的 main 函数。 而 zygote 进程进入一个循环，从而处理到来的 socket 消息。

```c
{
zygoteServer = new ZygoteServer(isPrimaryZygote);

if (startSystemServer) {
    Runnable r = forkSystemServer(abiList, zygoteSocketName, zygoteServer);

    // {@code r == null} in the parent (zygote) process, and {@code r != null} in the
    // child (system_server) process.
    if (r != null) { // forkSystemServer 进程
        r.run();
        return;
      }
    }

    Log.i(TAG, "Accepting command socket connections");

    // The select loop returns early in the child process after a fork and
    // loops forever in the zygote.
    // zygote 进程
    caller = zygoteServer.runSelectLoop(abiList);
}
```


# 应用进程启动

## 借助 Zygote 启动应用流程

1. Zygote 使用 epoll 监听 socket fd。
2. SystemServer 中的 AMS 向 Zygote 发送一个启动新进程的 Socket 消息
3. Zygote 收到启动新进程的 socket 消息后，fork 新进程并执行新进程的 main 函数 


