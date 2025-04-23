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

