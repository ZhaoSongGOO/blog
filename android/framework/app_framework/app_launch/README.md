# Android 应用程序进程的启动过程

ActivityManagerService 在启动一个应用程序组件时，如果发现这个组件所需要的应用程序进程还没有启动起来，那么它就会请求 Zygote 进程将这个应用程序进程启动起来。

Zygote 进程是通过复制自身的方式来创建一个新的应用程序进程的。由于 Zygote 进程在启动时会在内部创建一个虚拟机实例，因此，通过复制它而得到的应用程序进程就很自然地获得了一个虚拟机实例的拷贝。有了这个虚拟机实例之后，这个应用程序进程就可以将使用 Java 语言开发的应用程序组件运行起来了。

应用程序进程在启动的过程中，除了可以获得一个虚拟机实例之外，还可以获得一个 Binder 线程池和一个消息循环，这样，运行在它里面的应用程序组件就可以方便地使用 Android 系统的消息处理机制，以及 Binder 进程间通信机制来实现自己的业务逻辑。


## 应用程序进程的启动

### Step1: ActivityManagerService.startProcessLocked

```java
    private final void startProcessLocked(ProcessRecord app,
            String hostingType, String hostingNameStr) {
        //...
        
        try {
            int uid = app.info.uid;
            int[] gids = null;
            try {
                gids = mContext.getPackageManager().getPackageGids(
                        app.info.packageName);
            } catch (PackageManager.NameNotFoundException e) {
                //...
            }
            //...
            // 使用 Process 的 start 方法来触发进程创建。
            int pid = Process.start("android.app.ActivityThread",
                    mSimpleProcessManagement ? app.processName : null, uid, uid,
                    gids, debugFlags, null);
            //...
        } catch (RuntimeException e) {
            //...
        }
    }
```

### Step2: Process.start

```java
    public static final int start(final String processClass,
                                  final String niceName,
                                  int uid, int gid, int[] gids,
                                  int debugFlags,
                                  String[] zygoteArgs)
    {
        // 是否支持多进程，如果支持，就使用 zygote 去创建进程，不支持的话，走 else，用一个线程模拟应用进程。
        if (supportsProcesses()) {
            try {
                return startViaZygote(processClass, niceName, uid, gid, gids,
                        debugFlags, zygoteArgs);
            } catch (ZygoteStartFailedEx ex) {
                //...
            }
        } else {
            //...
        }
    }
```

### Step3: Process.startViaZygote

```java
    private static int startViaZygote(final String processClass,
                                  final String niceName,
                                  final int uid, final int gid,
                                  final int[] gids,
                                  int debugFlags,
                                  String[] extraArgs)
                                  throws ZygoteStartFailedEx {
        int pid;

        synchronized(Process.class) {
            ArrayList<String> argsForZygote = new ArrayList<String>();

            // --runtime-init, --setuid=, --setgid=,
            // and --setgroups= must go first
            // 这个参数标明，创建的新进程需要初始化运行时库，以及启动一个 binder 线程池
            argsForZygote.add("--runtime-init");
            //...
            //TODO optionally enable debuger
            //argsForZygote.add("--enable-debugger");

            // --setgroups is a comma-separated list
            //...
            // 请求 zygote 进程创建新进程
            pid = zygoteSendArgsAndGetPid(argsForZygote);
        }

        //...

        return pid;
    }
```

### Step4: Process.zygoteSendArgsAndGetPid

```java
static BufferedWriter sZygoteWriter;
private static int zygoteSendArgsAndGetPid(ArrayList<String> args)
        throws ZygoteStartFailedEx {

    int pid;
    // 创建一个连接到 Zygote 进程的 LocalSocket 对象
    openZygoteSocketIfNeeded();

    try {
        /**
         * See com.android.internal.os.ZygoteInit.readArgumentList()
         * Presently the wire format to the zygote process is:
         * a) a count of arguments (argc, in essence)
         * b) a number of newline-separated argument strings equal to count
         *
         * After the zygote process reads these it will write the pid of
         * the child or -1 on failure.
         */

        sZygoteWriter.write(Integer.toString(args.size()));
        sZygoteWriter.newLine();

        int sz = args.size();
        for (int i = 0; i < sz; i++) {
            String arg = args.get(i);
            if (arg.indexOf('\n') >= 0) {
                throw new ZygoteStartFailedEx(
                        "embedded newlines not allowed");
            }
            sZygoteWriter.write(arg);
            sZygoteWriter.newLine();
        }
        // 把创建所需的参数信息通过 socket 写入
        sZygoteWriter.flush();

        // Should there be a timeout on this?
        // 获取新创建的进程的 pid。
        pid = sZygoteInputStream.readInt();

        if (pid < 0) {
            throw new ZygoteStartFailedEx("fork() failed");
        }
    } catch (IOException ex) {
        //...
    }

    return pid;
}
```

`openZygoteSocketIfNeeded` 的实现如下。

```java
    // 用来与 Zygote 进程中一个名称为“zygote”的 Socket 建立连接的。
    // Zygote 进程在启动时，会在内部创建一个名称为“zygote”的 Socket，这个 Socket 是与设备文件/dev/socket/zygote 绑定在一起的
    static LocalSocket sZygoteSocket;
    private static void openZygoteSocketIfNeeded() 
            throws ZygoteStartFailedEx {

        int retryCount;

        if (sPreviousZygoteOpenFailed) {
            /*
             * If we've failed before, expect that we'll fail again and
             * don't pause for retries.
             */
            retryCount = 0;
        } else {
            retryCount = 10;            
        }

        /*
         * See bug #811181: Sometimes runtime can make it up before zygote.
         * Really, we'd like to do something better to avoid this condition,
         * but for now just wait a bit...
         */
        for (int retry = 0
                ; (sZygoteSocket == null) && (retry < (retryCount + 1))
                ; retry++ ) {

            if (retry > 0) {
                try {
                    Log.i("Zygote", "Zygote not up yet, sleeping...");
                    Thread.sleep(ZYGOTE_RETRY_MILLIS);
                } catch (InterruptedException ex) {
                    // should never happen
                }
            }

            try {
                // 创建一个 socket 对象
                sZygoteSocket = new LocalSocket();
                // 与 "zygote" 的 socket 进行连接
                sZygoteSocket.connect(new LocalSocketAddress(ZYGOTE_SOCKET, 
                        LocalSocketAddress.Namespace.RESERVED));

                // 绑定输入和输出流
                sZygoteInputStream
                        = new DataInputStream(sZygoteSocket.getInputStream());

                sZygoteWriter =
                    new BufferedWriter(
                            new OutputStreamWriter(
                                    sZygoteSocket.getOutputStream()),
                            256);

                Log.i("Zygote", "Process: zygote socket opened");

                sPreviousZygoteOpenFailed = false;
                break;
            } catch (IOException ex) {
                //...
                sZygoteSocket = null;
            }
        }

        if (sZygoteSocket == null) {
            sPreviousZygoteOpenFailed = true;
            throw new ZygoteStartFailedEx("connect failed");                 
        }
    }
```

### ZygoteConnection.runOnce

当 Zygote 进程接收到 Activity 管理服务 ActivityManagerService 发送过来的一个创建新的应用程序进程的请求之后，就会调用 ZygoteConnection 类的成员函数 runOnce 来处理这个请求。

```java
    boolean runOnce() throws ZygoteInit.MethodAndArgsCaller {

        String args[];
        Arguments parsedArgs = null;
        FileDescriptor[] descriptors;

        try {
            args = readArgumentList();
            descriptors = mSocket.getAncillaryFileDescriptors();
        } catch (IOException ex) {
            //...
        }

        //...

        int pid;

        try {
            parsedArgs = new Arguments(args);

            //...
            // 使用 fork 来创建子进程，并返回进程 id
            pid = Zygote.forkAndSpecialize(parsedArgs.uid, parsedArgs.gid,
                    parsedArgs.gids, parsedArgs.debugFlags, rlimits);
        } catch (IllegalArgumentException ex) {
            //...
        } catch (ZygoteSecurityException ex) {
            //...
        }

        if (pid == 0) {
            // in child
            // 使用 handleChildProc 来启动这个子进程。
            handleChildProc(parsedArgs, descriptors, newStderr);
            // should never happen
            return true;
        } else { /* pid != 0 */
            // in parent...pid of < 0 means failure
            return handleParentProc(pid, descriptors, parsedArgs);
        }
    }
```

### ZygoteConnection.handleChildProc

由于在前面的步骤中，Activity 管理服务 ActivityManagerService 在新创建的应用程序进程的启动参数列表中设置了一个 "--runtime-init" 参数，因此，这里传进来的 Arguments 对象 parsedArgs 的成员变量 runtimeInit 的值就会等于 true。

```java
    private void handleChildProc(Arguments parsedArgs,
            FileDescriptor[] descriptors, PrintStream newStderr)
            throws ZygoteInit.MethodAndArgsCaller {

        /*
         * Close the socket, unless we're in "peer wait" mode, in which
         * case it's used to track the liveness of this process.
         */
        //...

        if (parsedArgs.runtimeInit) {
            RuntimeInit.zygoteInit(parsedArgs.remainingArgs);
        } else {
            //...
        }
    }
```

### RuntimeInit.zygoteInit

```java
    public static final void zygoteInit(String[] argv)
            throws ZygoteInit.MethodAndArgsCaller {
        //...
        // 设置一些通用信息
        commonInit();
        // 启动一个 binder 线程池
        zygoteInitNative();

        //...
        // Remaining arguments are passed to the start class's static main

        String startClass = argv[curArg++];
        String[] startArgs = new String[argv.length - curArg];

        System.arraycopy(argv, curArg, startArgs, 0, startArgs.length);
        // 触发 android.app.ActivityThread 类的 main 方法。
        invokeStaticMain(startClass, startArgs);
    }
```

## Binder 线程池的启动

一个新的应用程序进程在创建完成之后，就会调用 RuntimeInit 类的静态成员函数 zygoteInitNative 来启动一个 Binder 线程池。

### Step1: RuntimeInit.zygoteInitNative

这个方法是一个 jni 方法，对应的 cpp 方法如下，这里 gCurRuntime 就是 AndroidRuntime，这个 onZygoteInit 方法被子类 AppRuntime 重写，因此这里本质上就是调用了 AppRuntime 的 onZygoteInit 方法。

```cpp
static void com_android_internal_os_RuntimeInit_zygoteInit(JNIEnv* env, jobject clazz)
{
    gCurRuntime->onZygoteInit();
}
```

### Step2: AppRuntime.onZygoteInit

调用当前应用程序进程中的 ProcessState 对象的成员函数 startThreadPool 来启动一个 Binder 线程池，以便使得当前应用程序进程可以通过 Binder 进程间通信机制来和其他进程通信。

```cpp
    virtual void onZygoteInit()
    {
        sp<ProcessState> proc = ProcessState::self();
        if (proc->supportsProcesses()) {
            LOGV("App process: starting thread pool.\n");
            proc->startThreadPool();
        }       
    }
```

## 消息循环的创建

一个新的应用程序进程在创建完成之后，就会调用 RuntimeInit 类的静态成员函数 invokeStaticMain 将 ActivityThread 类的静态成员函数 main 设置为新创建的应用程序进程的入口函数。ActivityThread 类的静态成员函数 main 在调用的过程中，就会在当前应用程序进程中创建一个消息循环。

### Step1: RuntimeInit.invokeStaticMain

```java
/*
className: android.app.ActivityThread
*/
    private static void invokeStaticMain(String className, String[] argv)
            throws ZygoteInit.MethodAndArgsCaller {

        // We want to be fairly aggressive about heap utilization, to avoid
        // holding on to a lot of memory that isn't needed.
        VMRuntime.getRuntime().setTargetHeapUtilization(0.75f);

        Class<?> cl;

        try {
            // 加载对应的类
            cl = Class.forName(className);
        } catch (ClassNotFoundException ex) {
            //...
        }

        Method m;
        try {
            m = cl.getMethod("main", new Class[] { String[].class });
        } catch (NoSuchMethodException ex) {
           //...
        } catch (SecurityException ex) {
           //...
        }
        //...

        /*
         * This throw gets caught in ZygoteInit.main(), which responds
         * by invoking the exception's run() method. This arrangement
         * clears up all the stack frames that were required in setting
         * up the process.
         */
        // 这个处理很神奇，没有选择直接调用，而是抛出一个异常。这个异常会被 ZygoteInit 的 main 函数捕获。
        // 这里就是想利用异常的栈解退机制，让整个进程的栈还原一下，以表现的像是一个新的进程。
        // 我认为这里的目的是避免异常排查时错误的堆栈带来误导。
        throw new ZygoteInit.MethodAndArgsCaller(m, argv);
    }
```

### Step2: ZygoteInit.main

```java
    public static void main(String argv[]) {
        try {
            //...

            if (ZYGOTE_FORK_MODE) {
                runForkMode();
            } else {
                runSelectLoopMode();
            }
            //... 这里捕获异常
        } catch (MethodAndArgsCaller caller) {
            caller.run();
        } catch (RuntimeException ex) {
            //...
        }
    }
```

### Step3: MethodAndArgsCaller.run

```java
    public static class MethodAndArgsCaller extends Exception
            implements Runnable {
        /** method to call */
        private final Method mMethod;

        /** argument array */
        private final String[] mArgs;

        public MethodAndArgsCaller(Method method, String[] args) {
            mMethod = method;
            mArgs = args;
        }

        public void run() {
            try {
                // 没什么特别的，直接 invoke
                mMethod.invoke(null, new Object[] { mArgs });
            } catch (IllegalAccessException ex) {
                throw new RuntimeException(ex);
            } catch (InvocationTargetException ex) {
                Throwable cause = ex.getCause();
                if (cause instanceof RuntimeException) {
                    throw (RuntimeException) cause;
                } else if (cause instanceof Error) {
                    throw (Error) cause;
                }
                throw new RuntimeException(ex);
            }
        }
    }
```

### Step4: ActivityThread.main

调用 Looper 类的静态成员函数 loop 进入到前面所创建的一个消息循环中。

```java
    public static final void main(String[] args) {
        //...

        Looper.prepareMainLooper();
        //...

        ActivityThread thread = new ActivityThread();
        thread.attach(false);

        //...

        Looper.loop();

        //...
    }
```