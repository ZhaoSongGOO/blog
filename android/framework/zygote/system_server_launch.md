# System 进程的启动过程

<img src="android/framework/zygote/resources/2.png" style="width:70%">

## Step1: ZygoteInit.handleSystemServerProcess

```java
    private static void handleSystemServerProcess(
            ZygoteConnection.Arguments parsedArgs)
            throws ZygoteInit.MethodAndArgsCaller {
        // 由于 System 进程复制了 Zygote 进程的地址空间，因此，它就会获得 Zygote 进程在启动过程中所创建的一个 Socket。System 进程不需要使用这个 Socket，
        // 因此，调用 ZygoteInit 类的静态成员函数 closeServerSocket 来关闭它
        closeServerSocket();

        /*
         * Pass the remaining arguments to SystemServer.
         * "--nice-name=system_server com.android.server.SystemServer"
         */
        // 创建 system server 
        RuntimeInit.zygoteInit(parsedArgs.remainingArgs);
        /* should never reach here */
    }
```

## Step2: RuntimeInit.zygoteInit

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
        // 触发 com.android.server.SystemServer 类的 main 方法。
        invokeStaticMain(startClass, startArgs);
    }
```

## Step3: SystemServer.main

```java
    public static void main(String[] args) {
        //...
        // 加载一个 c++ 动态库
        System.loadLibrary("android_servers");
        init1(args);
    }
    native public static void init1(String[] args);
```

## Step4: SystemServer.init1

init1 方法是一个 c++ 方法，实现如下。

```cpp
static void android_server_SystemServer_init1(JNIEnv* env, jobject clazz)
{
    // 调用了函数system_init来启动一些使用C++语言开发的系统服务
    system_init();
}

extern "C" status_t system_init()
{
    LOGI("Entered system_init()");
    
    sp<ProcessState> proc(ProcessState::self());
    
    // 获取 service manager
    sp<IServiceManager> sm = defaultServiceManager();
    LOGI("ServiceManager: %p\n", sm.get());
    
    // 注册一个死亡通知
    sp<GrimReaper> grim = new GrimReaper();
    sm->asBinder()->linkToDeath(grim, grim.get(), 0);
    
    // 启动SurfaceFlinger和SensorService两个服务，其中，SurfaceFlinger是一个与系统UI相关的服务，而SensorService是一个传感器服务
    char propBuf[PROPERTY_VALUE_MAX];
    property_get("system_init.startsurfaceflinger", propBuf, "1");
    if (strcmp(propBuf, "1") == 0) {
        // Start the SurfaceFlinger
        SurfaceFlinger::instantiate();
    }

    // Start the sensor service
    SensorService::instantiate();

    //...
    
    AndroidRuntime* runtime = AndroidRuntime::getRuntime();

    LOGI("System server: starting Android services.\n");
    // 初始化 java 编写的系统服务。
    runtime->callStatic("com/android/server/SystemServer", "init2");
        
    // If running in our own process, just go into the thread
    // pool.  Otherwise, call the initialization finished
    // func to let this process continue its initilization.
    if (proc->supportsProcesses()) {
        LOGI("System server: entering thread pool.\n");
        ProcessState::self()->startThreadPool();
        IPCThreadState::self()->joinThreadPool();
        LOGI("System server: exiting thread pool.\n");
    }
    return NO_ERROR;
}
```

## Step5: SystemServer.init2

创建了一个类型为ServerThread的线程并启动。

```java
    public static final void init2() {
        Slog.i(TAG, "Entered the Android system server!");
        Thread thr = new ServerThread();
        thr.setName("android.server.ServerThread");
        thr.start();
    }
```

## Step6: ServerThread.run

```java
    public void run() {
        //...

        Looper.prepare();
        //...
        // Critical services...
        try {
            //...

            Slog.i(TAG, "Activity Manager");
            context = ActivityManagerService.main(factoryTest);

            //...

            Slog.i(TAG, "Package Manager");
            pm = PackageManagerService.main(context,
                    factoryTest != SystemServer.FACTORY_TEST_OFF);

            ActivityManagerService.setSystemProcess();

            mContentResolver = context.getContentResolver();

            //...

            Slog.i(TAG, "Content Manager");
            ContentService.main(context,
                    factoryTest == SystemServer.FACTORY_TEST_LOW_LEVEL);

            //...

            Slog.i(TAG, "Window Manager");
            wm = WindowManagerService.main(context, power,
                    factoryTest != SystemServer.FACTORY_TEST_LOW_LEVEL);
            ServiceManager.addService(Context.WINDOW_SERVICE, wm);

            //...

        } catch (RuntimeException e) {
            Slog.e("System", "Failure starting core service", e);
        }

        //...

        Looper.loop();
        Slog.d(TAG, "System ServerThread is exiting!");
    }
```


