# Zygote 进程启动脚本以及启动流程

## Zygote 进程启动脚本

Zygote 进程是由 Android 系统的第一个进程 init 启动起来的。init 进程是在内核加载完成之后就启动起来的，它在启动的过程中，会读取根目录下的一个脚本文件 init.rc，以便可以将其他需要开机启动的进程也一起启动起来。

```cpp
/*
第 1 行表示 Zygote 进程是以服务的形式启动的，并且它所对应的应用程序文件为/system/bin/app_process。
接下来的四个选项是 Zygote 进程的启动参数，其中，最后一个参数"--start-system-server"表示 Zygote 进程在启动完成之后，需要马上将 System 进程也启动起来。
*/
service zygote /system/bin/app_process -Xzygote /system/bin --zygote --start-system-server
    /* 
    第 2 行表示 Zygote 进程在启动的过程中，需要在内部创建一个名称为"zygote"的 Socket。
    这个 Socket 是用来执行进程间通信的，它的访问权限被设置为 666，即所有用户都可以对它进行读和写。
    */
    socket zygote stream 666
```

init 进程的逻辑在 init.c 中，因为 zygote 被配置成 service 启动，这会触发其 service_start 方法来创建任务。

参数 svc 指向了一个 service 结构体，它的成员变量 sockets 和 args 分别保存了即将要启动的服务的 Socket 列表和静态启动参数列表。

> [execve 为何可以安全访问源进程数据 ENV](android/framework/zygote/ref/execve_visit_data_from_source_process.md)

```c
void service_start(struct service *svc, const char *dynamic_args)
{
    //...
    pid_t pid;
    //...

    pid = fork(); // fork 一个新进程，返回 0 意味着子进程。

    if (pid == 0) {
        struct socketinfo *si;
        //...
        // 遍历 socket 列表
        for (si = svc->sockets; si; si = si->next) {
            int socket_type = (
                    !strcmp(si->type, "stream") ? SOCK_STREAM :
                        (!strcmp(si->type, "dgram") ? SOCK_DGRAM : SOCK_SEQPACKET));
            // 创建 socket，返回的是文件描述符
            int s = create_socket(si->name, socket_type,
                                  si->perm, si->uid, si->gid);
            if (s >= 0) {
                // 发布 socket
                publish_socket(si->name, s);
            }
        }
        //...
        // 这里使用 execve 方法来启动 `/system/bin/app_process` 方法，并传入参数
        if (!dynamic_args) {
            if (execve(svc->args[0], (char**) svc->args, (char**) ENV) < 0) {
                ERROR("cannot execve('%s'): %s\n", svc->args[0], strerror(errno));
            }
        } else {
            char *arg_ptrs[INIT_PARSER_MAXARGS+1];
            int arg_idx = svc->nargs;
            char *tmp = strdup(dynamic_args);
            char *next = tmp;
            char *bword;

            /* Copy the static arguments */
            memcpy(arg_ptrs, svc->args, (svc->nargs * sizeof(char *)));

            while((bword = strsep(&next, " "))) {
                arg_ptrs[arg_idx++] = bword;
                if (arg_idx == INIT_PARSER_MAXARGS)
                    break;
            }
            arg_ptrs[arg_idx] = '\0';
            // Env 传递
            execve(svc->args[0], (char**) arg_ptrs, (char**) ENV);
        }
        _exit(127);
    }

    //...
}
```

下面我们分析一下 `create_socket` 和 `publish_socket` 两个方法的实现。

`create_socket` 就是创建一个 socket 套接字，并与文件 `/dev/socket/zygote` 绑定。

```c
int create_socket(const char *name, int type, mode_t perm, uid_t uid, gid_t gid)
{
    struct sockaddr_un addr;
    int fd, ret;

    fd = socket(PF_UNIX, type, 0);
    //...

    memset(&addr, 0 , sizeof(addr));
    addr.sun_family = AF_UNIX;
    // #define ANDROID_SOCKET_DIR		"/dev/socket"
    snprintf(addr.sun_path, sizeof(addr.sun_path), ANDROID_SOCKET_DIR"/%s",
             name);
    //...

    ret = bind(fd, (struct sockaddr *) &addr, sizeof (addr));
    //...

    chown(addr.sun_path, uid, gid);
    chmod(addr.sun_path, perm);

    //...

    return fd;
    //...
}
```

`publish_socket` 实现如下，首先将宏 ANDROID_SOCKET_ENV_PREFIX 和参数 name 所描述的两个字符串连接在一起，保存在字符串 key 中。宏 ANDROID_SOCKET_ENV_PREFIX 的值为"ANDROID_SOCKET_"​，而参数 name 的值为"zygote"​，因此，前面得到的字符串 key 的值就为"ANDROID_SOCKET_zygote"​。

```c
static void publish_socket(const char *name, int fd)
{
    // #define ANDROID_SOCKET_ENV_PREFIX	"ANDROID_SOCKET_"
    char key[64] = ANDROID_SOCKET_ENV_PREFIX;
    char val[64];

    strlcpy(key + sizeof(ANDROID_SOCKET_ENV_PREFIX) - 1,
            name,
            sizeof(key) - sizeof(ANDROID_SOCKET_ENV_PREFIX));
    snprintf(val, sizeof(val), "%d", fd);
    // 将这个 fd 设置为全局变量 ANDROID_SOCKET_zygote 的值，这个变量会被 fork 后的 exec 的时候传入。
    add_environment(key, val);

    /* make sure we don't close-on-exec */
    // 这行代码的作用是清除指定文件描述符 `fd` 上的 `FD_CLOEXEC` 标志。这样做的直接效果是，确保这个文件描述符 `fd` 在当前进程通过 `exec()` 系统调用启动一个新程序后，不会被自动关闭，而是会被这个新程序继承过去。
    fcntl(fd, F_SETFD, 0);
}
```

## Zygote 进程启动流程

<img src="android/framework/zygote/resources/1.png" style="width:70%">


### Step1: app_process.main

Zygote 进程中加载的应用程序文件为 system/bin/app_process。因此，接下来我们就从这个应用程序文件的入口函数 main 开始分析 Zygote 进程的启动过程。

```cpp
int main(int argc, const char* const argv[])
{
    // These are global variables in ProcessState.cpp
    mArgC = argc;
    mArgV = argv;
    
    mArgLen = 0;
    for (int i=0; i<argc; i++) {
        mArgLen += strlen(argv[i]) + 1;
    }
    mArgLen--;

    AppRuntime runtime;
    const char *arg;
    const char *argv0;

    argv0 = argv[0];

    // Process command line arguments
    // ignore argv[0]
    argc--;
    argv++;

    // Everything up to '--' or first non '-' arg goes to the vm
    
    int i = runtime.addVmArguments(argc, argv);

    // Next arg is parent directory
    if (i < argc) {
        runtime.mParentDir = argv[i++];
    }

    // Next arg is startup classname or "--zygote"
    if (i < argc) {
        arg = argv[i++];
        // 是不是启动的 zygote 进程
        if (0 == strcmp("--zygote", arg)) {
            bool startSystemServer = (i < argc) ? 
                    strcmp(argv[i], "--start-system-server") == 0 : false;
            setArgv0(argv0, "zygote");
            set_process_name("zygote");
            // 使用 runtime 的 start 方法进一步启动 zygote 进程。
            runtime.start("com.android.internal.os.ZygoteInit",
                startSystemServer);
        } else {
            set_process_name(argv0);

            runtime.mClassName = arg;

            // Remainder of args get passed to startup class main()
            runtime.mArgC = argc-i;
            runtime.mArgV = argv+i;

            LOGV("App process is starting with pid=%d, class=%s.\n",
                 getpid(), runtime.getClassName());
            runtime.start();
        }
    } else {
        LOG_ALWAYS_FATAL("app_process: no class name or --zygote supplied.");
        fprintf(stderr, "Error: no class name or --zygote supplied.\n");
        app_usage();
        return 10;
    }

}
```

### Step2: AndroidRuntime.start

AppRuntime 是 AndroidRuntime 的子类，start 方法执行的就是 AndroidRuntime 的 start 方法。

```cpp
/*
 className: "com.android.internal.os.ZygoteInit"
 startSystemServer: true
*/
void AndroidRuntime::start(const char* className, const bool startSystemServer)
{
    //...

    char* slashClassName = NULL;
    char* cp;
    JNIEnv* env;

    //...

    // 创建 java 虚拟机实例
    /* start the virtual machine */
    if (startVm(&mJavaVM, &env) != 0)
        goto bail;

    /*
     * Register android functions.
     */
    // 注册一系列的 jni 方法
    if (startReg(env) < 0) {
        LOGE("Unable to register all android natives\n");
        goto bail;
    }

    /*
     * We want to call main() with a String array with arguments in it.
     * At present we only have one argument, the class name.  Create an
     * array to hold it.
     */
    jclass stringClass;
    jobjectArray strArray;
    jstring classNameStr;
    jstring startSystemServerStr;

    stringClass = env->FindClass("java/lang/String");
    assert(stringClass != NULL);
    strArray = env->NewObjectArray(2, stringClass, NULL);
    assert(strArray != NULL);
    classNameStr = env->NewStringUTF(className);
    assert(classNameStr != NULL);
    env->SetObjectArrayElement(strArray, 0, classNameStr);
    startSystemServerStr = env->NewStringUTF(startSystemServer ? 
                                                 "true" : "false");
    env->SetObjectArrayElement(strArray, 1, startSystemServerStr);

    /*
     * Start VM.  This thread becomes the main thread of the VM, and will
     * not return until the VM exits.
     */
    jclass startClass;
    jmethodID startMeth;

    slashClassName = strdup(className);
    for (cp = slashClassName; *cp != '\0'; cp++)
        if (*cp == '.')
            *cp = '/';

    startClass = env->FindClass(slashClassName);
    if (startClass == NULL) {
        //...
    } else {
        startMeth = env->GetStaticMethodID(startClass, "main",
            "([Ljava/lang/String;)V");
        if (startMeth == NULL) {
            LOGE("JavaVM unable to find main() in '%s'\n", className);
            /* keep going */
        } else {
            // 通过 jni 调用 "com.android.internal.os.ZygoteInit" 类的 main 方法。
            env->CallStaticVoidMethod(startClass, startMeth, strArray);

#if 0
            if (env->ExceptionCheck())
                threadExitUncaughtException(env);
#endif
        }
    }

    //...
}
```

### Step3: ZygoteInit.main

```java
    public static void main(String argv[]) {
        try {
            //...
            // 创建一个 server 端的 socket，用来等待 AMS 请求 zygote 进程创建新的应用程序进程
            registerZygoteSocket();
            //...

            if (argv[1].equals("true")) {
                // 启动 system server 进程
                startSystemServer();
            } //...
            //...

            if (ZYGOTE_FORK_MODE) { // 这里一般是 false
                runForkMode(); // zygote 在收到 AMS 请求后，会单独 fork 一个进程去处理。
            } else {
                runSelectLoopMode(); // zygote 收到 AMS 请求后，会在当前进程中处理。
            }

            //...
        } catch (MethodAndArgsCaller caller) {
            //...
        } catch (RuntimeException ex) {
            //...
        }
    }
```

### Step4: ZygoteInit.registerZygoteSocket

```java
private static final String ANDROID_SOCKET_ENV = "ANDROID_SOCKET_zygote";
private static void registerZygoteSocket() {
    if (sServerSocket == null) {
        int fileDesc;
        try {
            // 获得一个名称为“ANDROID_SOCKET_zygote”的环境变量的值，接着将它转换为一个文件描述符。
            String env = System.getenv(ANDROID_SOCKET_ENV);
            fileDesc = Integer.parseInt(env);
        } catch (RuntimeException ex) {
            //...
        }

        try {
            // 根据这个文件描述符来创建一个 Server 端 Socket，并且保存在 ZygoteInit 的静态成员变量 sServerSocket 中
            sServerSocket = new LocalServerSocket(
                    createFileDescriptor(fileDesc));
        } catch (IOException ex) {
            //...
        }
    }
}
```

### Step5: ZygoteInit.startSystemServer

```java
    private static boolean startSystemServer()
            throws MethodAndArgsCaller, RuntimeException {
        /* Hardcoded command line to start the system server */
        String args[] = {
            "--setuid=1000",
            "--setgid=1000",
            "--setgroups=1001,1002,1003,1004,1005,1006,1007,1008,1009,1010,3001,3002,3003",
            "--capabilities=130104352,130104352",
            "--runtime-init",
            "--nice-name=system_server",
            "com.android.server.SystemServer",
        };
        ZygoteConnection.Arguments parsedArgs = null;

        int pid;

        try {
            parsedArgs = new ZygoteConnection.Arguments(args);
            //...
            // 创建 system server 进程
            pid = Zygote.forkSystemServer(
                    parsedArgs.uid, parsedArgs.gid,
                    parsedArgs.gids, debugFlags, null,
                    parsedArgs.permittedCapabilities,
                    parsedArgs.effectiveCapabilities);
        } catch (IllegalArgumentException ex) {
            //...
        }

        /* For child process */
        if (pid == 0) {
            // 调用静态成员函数 handleSystemServerProcess 来启动 System 进程
            handleSystemServerProcess(parsedArgs);
        }

        return true;
    }
```

### Step6: ZygoteInit.runSelectLoopMode

```java
/**
 * The number of times that the main Zygote loop
 * should run before calling gc() again.
 */
static final int GC_LOOP_COUNT = 10;
private static void runSelectLoopMode() throws MethodAndArgsCaller {
    ArrayList<FileDescriptor> fds = new ArrayList();
    ArrayList<ZygoteConnection> peers = new ArrayList();
    // 创建了一个尺寸为 4 的 socket 文件描述符数组，表示最多可以同时处理 4 个 socket 连接。
    FileDescriptor[] fdArray = new FileDescriptor[4];

    fds.add(sServerSocket.getFileDescriptor());
    peers.add(null);

    int loopCount = GC_LOOP_COUNT;
    while (true) {
        int index;

        /*
            * Call gc() before we block in select().
            * It's work that has to be done anyway, and it's better
            * to avoid making every child do it.  It will also
            * madvise() any free memory as a side-effect.
            *
            * Don't call it every time, because walking the entire
            * heap is a lot of overhead to free a few hundred bytes.
            */
        if (loopCount <= 0) {
            gc();
            loopCount = GC_LOOP_COUNT;
        } else {
            loopCount--;
        }


        try {
            fdArray = fds.toArray(fdArray);
            // 使用 select 来监控数据是否到达
            index = selectReadable(fdArray);
        } catch (IOException ex) {
            throw new RuntimeException("Error in select()", ex);
        }

        if (index < 0) {
            throw new RuntimeException("Error in select()");
        } else if (index == 0) {
            // Activity 管理服务 ActivityManagerService 通过 ZygoteInit 类的静态成员变量 sServerSocket 所描述的一个 Socket 与 Zygote 进程建立了新的连接。
            ZygoteConnection newPeer = acceptCommandPeer();
            peers.add(newPeer);
            fds.add(newPeer.getFileDesciptor());
        } else {
            // 如果变量 index 的值大于 0，那么就说明 Activity 管理服务 ActivityManagerService 向 Zygote 进程发送了一个创建应用程序进程的请求。
            boolean done;
            done = peers.get(index).runOnce(); // 处理请求
            // 处理完成，删除
            if (done) {
                peers.remove(index);
                fds.remove(index);
            }
        }
    }
}
```

