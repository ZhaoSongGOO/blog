# Android 应用程序线程的消息循环模型

Android 应用程序是支持多线程的。Android 应用程序线程有主线程和子线程之分，其中，主线程是由 Activity 管理服务 ActivityManagerService 请求 Zygote 进程创建的；而子线程是由主线程或者其他子线程创建的。

## 主线程消息循环模型

前面我们知道，AMS 会通过 Process 的 start 方法给 Zygote 进程发送 socket 通信。在本次通信中会发送 ActivityThread 的类名，使得 Zygote 进程 fork 并且加载 ActivityThread 类，最终调用 ActivityThread 的 main 方法完成一个应用进程的创建。

在 ActivityThread 的 main 方法中，会使用 prepareMainLooper 和 loop 方法来启动主线程的消息循环。

```java
    public static final void main(String[] args) {
        //...

        Looper.prepareMainLooper();
        //...   

        Looper.loop();

        //...
    }
```

## 与界面无关的子线程消息循环模型

> [局部变量 thread 是否会被 gc 回收?](android/framework/app_framework/ref/handle_gc.md)

在 Android 中我们可以通过 Thread 创建一个子线程，并在其 run 方法中实现自己的子线程逻辑，但是需要注意，这个子线程是不具有消息循环的，会在执行完成 run 方法后销毁。

Android 提供了 HandlerThread 类，这个类可以创建一个消息循环，后续我们可以将 Message 发送给这个循环进行处理。

## 与界面相关的子线程消息循环模型

首先有个前提就是，我们不能在非主线程执行任何 UI 相关操作。

我们通过分析历史版本中的 [AsyncTask](android/framework/app_framework/ref/async_task.md) 类来明确一下使用方式。

`AsyncTask` 通过四个核心的回调方法来组织整个工作流程。它使用了泛型 `<Params, Progress, Result>`：
- `Params`: 启动任务时传入的参数类型。
- `Progress`: 后台任务执行中，发布进度的参数类型。
- `Result`: 后台任务执行完毕后，返回结果的参数类型。
这四个方法按生命周期顺序执行：
1. `onPreExecute()`
  - 线程：UI 线程。
  - 时机：在后台任务 `doInBackground()` 执行之前调用。
  - 作用：进行任务开始前的准备工作，比如显示一个加载中的 `ProgressBar`。
2. `doInBackground(Params... params)`
  - 线程：后台线程（工作线程）。
  - 时机：`onPreExecute()` 执行完毕后立即执行。
  - 作用：这是唯一一个在后台线程执行的方法，所有耗时操作都必须在这里完成。你可以通过 `publishProgress()` 方法来发布进度。方法的返回值会作为参数传递给 `onPostExecute()`。
3. `onProgressUpdate(Progress... values)`
  - 线程：UI 线程。
  - 时机：在 `doInBackground()` 中调用 `publishProgress()` 后被触发。
  - 作用：在界面上更新任务进度，比如更新 `ProgressBar` 的进度条。
4. `onPostExecute(Result result)`
  - 线程：UI 线程。
  - 时机：`doInBackground()` 执行完毕并返回结果后调用。
  - 作用：处理后台任务的结果，更新 UI。比如隐藏 `ProgressBar`，并将数据显示在 `TextView` 上。

上面是 AsyncTask 的简单使用介绍，下面我们深入分析一下内部的源码。

### AsyncTask 数据成员介绍

```java
/*
    AsyncTask<String, Void, Bitmap> -> AsyncTask<Params, Progress, Result>
    这里是对应的，标明一步任务的输入数据，过程数据和结果数据
*/
public abstract class AsyncTask<Params, Progress, Result> {
    //...
    // 工作任务队列
    /*
    这个队列的特征：
    (1)一个线程如果试图从一个空的 LinkedBlockingQueue 队列中取出一个工作任务来执行，那么它就会被阻塞，直到这个队列有新的工作任务添加进来为止。
    (2)一个线程如果试图往一个满的 LinkedBlockingQueue 队列中添加一个新的工作任务，那么它同样会被阻塞，直到这个队列腾出来新的空闲位置为止。
    */
    private static final BlockingQueue<Runnable> sWorkQueue =
            new LinkedBlockingQueue<Runnable>(10);

    /*
    异步任务类 AsyncTask 的静态成员变量 sThreadFactory 指向了一个类型为 ThreadFactory 的线程创建工厂，
    它创建出来的线程是用来执行保存在静态成员变量 sWorkQueue 中的工作任务的。
    */
    private static final ThreadFactory sThreadFactory = new ThreadFactory() {
        private final AtomicInteger mCount = new AtomicInteger(1);

        public Thread newThread(Runnable r) {
            return new Thread(r, "AsyncTask #" + mCount.getAndIncrement());
        }
    };
    //...
    /*
    异步任务类 AsyncTask 的静态成员变量 sExecutor 指向了一个类型为 ThreadPoolExecutor 的线程池，保存在这个线程池中的线程就是通过静态成员变量 sThreadFactory 来创建的，
    并且用来执行保存在静态成员变量 sWorkQueue 中的工作任务。
    */
    private static final ThreadPoolExecutor sExecutor = new ThreadPoolExecutor(CORE_POOL_SIZE,
            MAXIMUM_POOL_SIZE, KEEP_ALIVE, TimeUnit.SECONDS, sWorkQueue, sThreadFactory);

    private static final int MESSAGE_POST_RESULT = 0x1;
    private static final int MESSAGE_POST_PROGRESS = 0x2;
    private static final int MESSAGE_POST_CANCEL = 0x3;

    private static final InternalHandler sHandler = new InternalHandler();

    private final WorkerRunnable<Params, Result> mWorker;
    private final FutureTask<Result> mFuture;
    //...
}
```

这里大多数的成员都是 static 的，这也就意味着在一个应用程序进程中，这些成员是共用的。对于成员 sHandler 会在 AsyncTask 第一次被使用的时候进行初始化，此时 InternalHandler 就绑定了 looper，至于是哪一个 looper 取决于我们在哪个线程中第一次使用了 AsyncTask，在 Android 的设计中，就是主线程。

总结下，就是 Async 中持有了一个绑定了主线程 looper 的 handler，以将任务派发到主线程执行，同时持有一个线程池，用来执行 background 任务。

