# Android 面试知识点

> 本文总阅读量 <span id="busuanzi_value_page_pv"><i class="fa fa-spinner fa-spin"></i></span>次
--- 

## 四大组件

### Activity

Activity（活动） 是 Android 四大组件之一，代表一个用户交互界面（UI 屏幕），用于展示应用内容并与用户进行交互。每个 Activity 都是一个独立的界面单元，例如：

- 微信的“聊天窗口”是一个 Activity。
- 淘宝的“商品详情页”是另一个 Activity。

#### 生命周期

<img src="android/interview/resources/a_1.png" style="width:70%">

##### 系统部分

当我们点击一个应用图标或者调用 `startActivity` 启动一个新的 `activity` 的时候，framwork 将会创建一个新的 `activity`，大致过程如下: 创建 `activity` 的操作通过 Binder IPC 调用了 AMS(ActivityManagerService) 服务。该服务进行权限以及启动模式的检查后，触发对应的应用创建 `activity`。

##### 应用部分

1. 应用做了基本初始化后，调用 `onCreate` 回调。用户可以在这个回调中做一些初始布局文件的绑定等操作。
2. 随后应用由不可见状态变成可见状态, 调用 `onStart` 函数。此时虽然可见，但是不可交互，处于一种尚未获取焦点的状态。
3. 随后应用获取焦点，变的可交互，此时调用 `onResume` 回调。
4. 如果另外一个 `activity` 启动遮挡了当前 `activity`, 在没有完全遮挡的时候，调用 `onPause` 方法。
5. 如果弹出的 `activity` 没有进一步遮挡，那在弹出的 `activity` 返回后，会调用 `onResume` 方法。进入第三步。
6. 如果进一步的这个 `activity` 被完全遮挡，调用 `onStop` 方法。
7. 调用 `onStop` 方法的页面后续重新进入前台后，会被调用 `onRestart` 方法。进入第二步。
8. 特别需要注意的是，调用 `onPause` 和 `onStop` 的 `activity` 在系统内存不足的时候，有可能会被系统回收，此时如果再返回，会进入第一步。
9. 如果彻底销毁，会调用 `onDestory` 方法。

#### 启动模式

##### standard

对于使用 standard 模式的 `activity`，系统不会在乎这个 `activity` 是否已经在返回栈中存在，每次启动都会创建一个该 `activity` 的新实例。

##### singleTop

当 `activity` 的启动模式指定为 `singleTop`，在启动 `activity` 时如果发现返回栈的栈顶已经是该 `activity`，则认为可以直接使用它，不会再创建新的 `activity` 实例。

##### singleTask

当 `activity` 的启动模式指定为 `singleTask`，每次启动该 `activity` 时，系统首先会在返回栈中检查是否存在该 `activity` 的实例，如果发现已经存在则直接使用该实例，并把在这个 `activity` 之上的所有其他 `activity` 统统出栈，如果没有发现就会创建一个新的 `activity` 实例。

##### singleInstance

<img src="android/interview/resources/a_2.png" style="width:50%">

`activity` 会独占一个全新的任务栈（Task），且该栈中只能存在该 `activity` 的实例。

##### singleInstancePerTask

如果从 不同任务栈 `singleInstancePerTask` 启动同一个  `activity`，每个栈会创建自己的实例。如果 同一任务栈 内再次启动该 Activity，会复用现有实例。主要是为了解决想要创建多个实例的同时又不想被无限创建的情况，即受限多实例。

- 多屏/多窗口: 在分屏或自由窗口模式下，允许同一 Activity 在不同窗口（任务栈）中独立存在。

```kotlin
// 左屏启动
val intentLeft = Intent(this, DetailActivity::class.java).apply {
    flags = Intent.FLAG_ACTIVITY_LAUNCH_ADJACENT // 分屏启动
}
startActivity(intentLeft)

// 右屏启动（会创建另一个实例）
val intentRight = Intent(this, DetailActivity::class.java).apply {
    flags = Intent.FLAG_ACTIVITY_LAUNCH_ADJACENT
}
startActivity(intentRight)
```


#### Fragment

Fragment是一种可以嵌入在Activity当中的UI片段，它能让程序更加合理和充分地利用大屏幕的空间，因而在平板上应用得非常广泛。

##### 设计 Fragment

1. 设置对应的 `xml` 文件

2. 编写对应的 `Fragment` 类，该类最好继承自 AndroidX 下面的 `Fragment`。并重写 `onCreateView` 方法。在该方法中加载对应的布局文件。

##### 静态加载

1. 在想要使用该 `Fragment` 的 `Activity` 的布局文件中以 `<fragment>` 来引入对应的 `Fragment`。

2. :exclamation: 需要注意的是，想使用 `Fragment` 的 `Activity` 必须继承自 `androidx.appcompat.app.AppCompatActivity`。否则会报错。

```xml
<fragment
    android:id="@+id/left"  // 必须提供id
    android:name="com.uiapp.lion.fragments.LeftFragment"  // Fragment 的完整包名
    android:layout_width="100dp"
    android:layout_height="match_parent" />
```

##### 动态加载

```kotlin
private fun replace(fragment: Fragment) {
    val fragmentManager = supportFragmentManager
    val transaction = fragmentManager.beginTransaction()
    transaction.replace(R.id.container, fragment)
    transaction.commit()
}
```


默认的情况下，当你的 fragment 被 replace 后，旧的会被直接销毁，所以可以使用 addToBackStack 将其增加到返回站，你在点击back后可以返回上 Fragment。

```kotlin
class MainActivity : AppCompatActivity() {

    ...

    private fun replaceFragment(fragment: Fragment) {
        val fragmentManager = supportFragmentManager
        val transaction = fragmentManager.beginTransaction()
        transaction.replace(R.id.rightLayout, fragment)
        transaction.addToBackStack(null) 
        transaction.commit()
    }

}
```

##### Fragment 与 Activity 交互

1. 在 Activity 中获取 Fragment

```kotlin
val fragment = supportFragmentManager.findFragmentById(R.id.leftFrag) as LeftFragment
```


2. 在 Fragment 获取所属的 Activit
```kotlin
val activity = getActivity()
if (activity != null) {
    val mainActivity = activity as MainActivity
}
```


##### Fragment 生命周期

<img src="android/interview/resources/a_3.png" style="width:90%">

###### 状态
1. 运行
当关联的activity处于运行状态时，fragment也处于运行状态。
2. 暂停
当一个activity进入到暂停状态，fragment也会处于运行状态。
3. 停止
当一个Activity进入停止状态时，与它相关联的Fragment就会进入停止状态，或者通过调用FragmentTransaction的remove()、replace()方法将Fragment从Activity中移除，但在事务提交之前调用了addToBackStack()方法，这时的Fragment也会进入停止状态
4. 销毁
Fragment总是依附于Activity而存在，因此当Activity被销毁时，与它相关联的Fragment就会进入销毁状态。或者通过调用FragmentTransaction的remove()、replace()方法将Fragment从Activity中移除，但在事务提交之前并没有调用addToBackStack()方法，这时的Fragment也会进入销毁状态。

###### 静态加载的 Fragment 生命周期

```txt
2025-05-14 13:12:15.541 14040-14040 LionTag                 com.uiapp.lion                       D  Fragment->onAttach
2025-05-14 13:12:15.541 14040-14040 LionTag                 com.uiapp.lion                       D  Fragment->onCreate
2025-05-14 13:12:15.541 14040-14040 LionTag                 com.uiapp.lion                       D  Fragment->onCreateView
2025-05-14 13:12:15.545 14040-14040 LionTag                 com.uiapp.lion                       D  Activity->onCreate
2025-05-14 13:12:15.547 14040-14040 LionTag                 com.uiapp.lion                       D  Activity->onStart
2025-05-14 13:12:15.547 14040-14040 LionTag                 com.uiapp.lion                       D  Fragment->onStart
2025-05-14 13:12:15.549 14040-14040 LionTag                 com.uiapp.lion                       D  Activity->onResume
2025-05-14 13:12:15.549 14040-14040 LionTag                 com.uiapp.lion                       D  Fragment->onResume
2025-05-14 13:16:35.106 14040-14040 LionTag                 com.uiapp.lion                       D  Activity->onPause
2025-05-14 13:16:35.106 14040-14040 LionTag                 com.uiapp.lion                       D  Fragment->onPause
2025-05-14 13:16:35.552 14040-14040 LionTag                 com.uiapp.lion                       D  Activity->onStop
2025-05-14 13:16:35.553 14040-14040 LionTag                 com.uiapp.lion                       D  Fragment->onStop
2025-05-14 13:16:35.555 14040-14040 LionTag                 com.uiapp.lion                       D  Activity->onDestroy
2025-05-14 13:16:35.556 14040-14040 LionTag                 com.uiapp.lion                       D  Fragment->onDestroyView
2025-05-14 13:16:35.557 14040-14040 LionTag                 com.uiapp.lion                       D  Fragment->onDestroy
2025-05-14 13:16:35.557 14040-14040 LionTag                 com.uiapp.lion                       D  Fragment->onDetach
```

###### 动态加载 Fragment 生命周期

```txt
2025-05-14 13:19:10.103 16411-16411 LionTag                 com.uiapp.lion                       D  Activity->onCreate
2025-05-14 13:19:10.109 16411-16411 LionTag                 com.uiapp.lion                       D  Activity->onStart
2025-05-14 13:19:10.110 16411-16411 LionTag                 com.uiapp.lion                       D  Activity->onResume
2025-05-14 13:19:11.797 16411-16411 LionTag                 com.uiapp.lion                       D  Fragment->onAttach
2025-05-14 13:19:11.798 16411-16411 LionTag                 com.uiapp.lion                       D  Fragment->onCreate
2025-05-14 13:19:11.798 16411-16411 LionTag                 com.uiapp.lion                       D  Fragment->onCreateView
2025-05-14 13:19:11.812 16411-16411 LionTag                 com.uiapp.lion                       D  Fragment->onStart
2025-05-14 13:19:11.814 16411-16411 LionTag                 com.uiapp.lion                       D  Fragment->onResume
2025-05-14 13:19:14.107 16411-16411 LionTag                 com.uiapp.lion                       D  Activity->onPause
2025-05-14 13:19:14.107 16411-16411 LionTag                 com.uiapp.lion                       D  Fragment->onPause
2025-05-14 13:19:14.554 16411-16411 LionTag                 com.uiapp.lion                       D  Activity->onStop
2025-05-14 13:19:14.554 16411-16411 LionTag                 com.uiapp.lion                       D  Fragment->onStop
2025-05-14 13:19:14.556 16411-16411 LionTag                 com.uiapp.lion                       D  Activity->onDestroy
2025-05-14 13:19:14.557 16411-16411 LionTag                 com.uiapp.lion                       D  Fragment->onDestroyView
2025-05-14 13:19:14.559 16411-16411 LionTag                 com.uiapp.lion                       D  Fragment->onDestroy
2025-05-14 13:19:14.559 16411-16411 LionTag                 com.uiapp.lion                       D  Fragment->onDetach
```

### Service

#### 什么是 Service？

Service是Android中实现程序后台运行的解决方案，它非常适合执行那些不需要和用户交互而且还要求长期运行的任务。

1. Service的运行不依赖于任何用户界面，即使程序被切换到后台，或者用户打开了另外一个应用程序，Service仍然能够保持正常运行。

2. 不过需要注意的是，Service并不是运行在一个独立的进程当中的，而是依赖于创建Service时所在的应用程序进程。当某个应用程序进程被杀掉时，所有依赖于该进程的Service也会停止运行。

3. 另外，也不要被Service的后台概念所迷惑，实际上Service并不会自动开启线程，所有的代码都是默认运行在主线程当中的。也就是说，我们需要在Service的内部手动创建子线程，并在这里执行具体的任务，否则就有可能出现主线程被阻塞的情况。

#### 普通Service

普通的service会在应用在前台的时候，维持在后台运行，但是当应用进入后台的时候，Service随时都有可能被系统回收。

1. 开发自己的 Service

```kotlin
class MyServices: Service() {
    // 与activity建立关联的接口
    override fun onBind(p0: Intent?): IBinder? {
        TODO("Not yet implemented")
    }

    // service 创建的时候调用
    override fun onCreate() {
        super.onCreate()
    }

    // service 启动的时候调用
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return super.onStartCommand(intent, flags, startId)
    }

    // service 销毁的时候调用
    override fun onDestroy() {
        super.onDestroy()
    }
}
```

2. XML 中注册
> 需要注意的是，四大组件都需要在 XML 中注册后才能使用

```xml
<service android:name=".MyServices" />
```

3. 一次性通信：start/stop service

在 start 的时候，如果这是第一次 start `service`, 那就会按照 `onCreate` -> `onStartCommand` 的方式去执行。如果之前 `service` 已经被 start 过，就不会再次被创建，直接调用 `onStartCommand`。
在 stop 的时候，直接调用 `OnDestory` 方法。如果对于一个没有 start 的 `service` 进行 stop，那不会有任何效果。

```kotlin
class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        startServiceBtn.setOnClickListener {
            val intent = Intent(this, MyService::class.java)
            startService(intent) // 启动Service
        }
        stopServiceBtn.setOnClickListener {
            val intent = Intent(this, MyService::class.java)
            stopService(intent) // 停止Service
        }
    }

}
```

4. 持久通信: bind/ubbind service

在持久通信中，和 service 建立通信的对象都会获得同一个 Binder 实例。

使用 bind 的时候，如果是第一次创建连接，那就调用 `onCreate` -> `onBind` 方法，并将 `onBind` 方法返回的 `Binder` 返回给连接对象。 对象A尝试在连接的状态下再次连接，将不会有任何的反应。

可以有多个对象通过 bind 连接上 service，后续建立连接的对象将不会执行 `onBind` 方法，而是直接返回对应的 `Binder` 对象。

unbind 的时候，会调用 `onDestory` 方法。对于一个没有 bind 的 链接，调用 unbind 会发生异常。

```kotlin
class MyService : Service() {
    private val mBinder = DownloadBinder()
    
    // 首先我们在service中实现一个binder，并在onBind方法中返回这个对象的实例
    class DownloadBinder : Binder() {

        fun startDownload() {
            Log.d("MyService", "startDownload executed")
        }

        fun getProgress(): Int {
            Log.d("MyService", "getProgress executed")
            return 0
        }

    }

    override fun onBind(intent: Intent): IBinder {
        return mBinder
    }
    ...
}


class MainActivity : AppCompatActivity() {

    lateinit var downloadBinder: MyService.DownloadBinder
    
    // 实现一个connect，重写对应的方法，
    private val connection = object : ServiceConnection {
        // onServiceConnected()方法方法会在Activity与Service成功绑定的时候调用
        // 这里面会拿到bind方法返回的binder
        override fun onServiceConnected(name: ComponentName, service: IBinder) {
            downloadBinder = service as MyService.DownloadBinder
            downloadBinder.startDownload()
            downloadBinder.getProgress()
        }
        
        // onServiceDisconnected()方法只有在Service的创建进程崩溃或者被杀掉的时候才会调用
        override fun onServiceDisconnected(name: ComponentName) {
        }

    }

    override fun onCreate(savedInstanceState: Bundle?) {
        ...
        bindServiceBtn.setOnClickListener {
            val intent = Intent(this, MyService::class.java)
            // BIND_AUTO_CREATE： 绑定后就创建, 这里我们不需要编写service的其余方法，
            // 因为我们操作主要是放在 binder里面。
            bindService(intent, connection, Context.BIND_AUTO_CREATE) // 绑定Service
        }
        unbindServiceBtn.setOnClickListener {
            unbindService(connection) // 解绑Service
        }
    }

}
```

#### 生命周期总结

1. 一旦在项目的任何位置调用了 Context 的 startService()方法，相应的 Service 就会启动，并回调 onStartCommand() 方法。如果这个Service之前还没有创建过，onCreate()方法会先于onStartCommand()方法执行。Service启动了之后会一直保持运行状态，直到stopService()或stopSelf()方法被调用，或者被系统回收。注意，虽然每调用一次startService()方法，onStartCommand()就会执行一次，但实际上每个Service只会存在一个实例。所以不管你调用了多少次startService()方法，只需调用一次stopService()或stopSelf()方法，Service就会停止。
2. 还可以调用Context的bindService()来获取一个Service的持久连接，这时就会回调Service中的onBind()方法。如果这个Service之前还没有创建过，onCreate()方法会先于onBind()方法执行。之后，调用方可以获取到onBind()方法里返回的IBinder对象的实例，这样就能自由地和Service进行通信了。只要调用方和Service之间的连接没有断开，Service就会一直保持运行状态，直到被系统回收。
3. 当调用了startService()方法后，再去调用stopService()方法。这时Service中的onDestroy()方法就会执行，表示Service已经销毁了。类似地，当调用了bindService()方法后，再去调用unbindService()方法，onDestroy()方法也会执行，这两种情况都很好理解。
4. 但是需要注意，我们是完全有可能对一个Service既调用了startService()方法，又调用了bindService()方法的，在这种情况下该如何让Service销毁呢？根据Android系统的机制，一个Service只要被启动或者被绑定了之后，就会处于运行状态，必须要让以上两种条件同时不满足，Service才能被销毁。所以，这种情况下要同时调用stopService()和unbindService()方法，onDestroy()方法才会执行。


#### 前台 service

前台Service和普通Service最大的区别就在于，它一直会有一个正在运行的图标在系统的状态栏显示，下拉状态栏后可以看到更加详细的信息，非常类似于通知的效果。

1. 编写前台 service 代码

```kotlin
class NotifyService : Service() {
    override fun onBind(intent: Intent?): IBinder? {
        return null
    }

    override fun onStartCommand(
        intent: Intent?,
        flags: Int,
        startId: Int,
    ): Int {
        val manager =
            getSystemService(NOTIFICATION_SERVICE) as
                NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel =
                NotificationChannel(
                    "NotifyService",
                    "NotifyService Notify",
                    NotificationManager.IMPORTANCE_DEFAULT,
                )
            manager.createNotificationChannel(channel)
        }
        val notificationIntent = Intent(this, ZygoteActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(this, 0, notificationIntent, PendingIntent.FLAG_MUTABLE)

        val notification =
            NotificationCompat.Builder(this, "NotifyService")
                .setContentTitle("This is content title")
                .setContentText("This is content text")
                .setSmallIcon(R.drawable.icon)
                .setLargeIcon(BitmapFactory.decodeResource(resources, R.drawable.icon_dark))
                .setContentIntent(pendingIntent)
                .build()

        // 将服务设置为前台服务
        startForeground(1, notification)

        return START_NOT_STICKY
    }
}
```

2. xml 注册，并添加权限

```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />

<application> 
    <service android:name=".services.NotifyService" android:foregroundServiceType="mediaProcessing" />
</application>
```


#### Android 线程

##### Thread

> 如何结束一个 Thread 创建的线程?
> 对于不执行阻塞任务的线程，无需关心，运行完成后会自动停止。
> 如果我们就想手动终止一个线程，或者必须手动终止(例如下面这个无限循环的，在整个进程退出前，它都不会销毁, 更严重的是， JVM 在退出前会等待所有线程执行完成才会退出)。那就需要对其调用 interrupt.
> 需要注意的是 interrupt 不会直接中断线程，只是将其设置成中断状态，只有这个线程 block 中包含阻塞调用，才会直接触发 InterruptedException 来进行中断。如果我们不包含阻塞调用，那就要手动判断中断状态以适时退出。
> 同时还有一个更加简单的操作，我们可以对线程设置成 `Daemon`, 这样 JVM 在退出前不会等待他，而是直接销毁。

```kotlin
package com.uiapp.render

import java.util.concurrent.LinkedBlockingQueue

class Actor {
    var actorThread: Thread
    var taskQueue: LinkedBlockingQueue<() -> Unit> = LinkedBlockingQueue<() -> Unit>()

    init {
        // 创建一个线程
        actorThread =
            Thread {
                try {
                    while (true) {
                        val task = taskQueue.take() // 阻塞调用，含有阻塞调用的线程逻辑，会在被 interrupt的时候，触发 InterruptedException
                        task()
                    }
                } catch (e: InterruptedException) {
                    print("catch InterruptedException\n")
                    Thread.currentThread().interrupt()
                }
            }
    }

    fun start()  {
        actorThread.start() // 线程启动
    }

    fun postTask(task: () -> Unit) {
        taskQueue.put(task) // 向任务队列中拋送任务
    }

    fun stop()  {
        actorThread.interrupt() // 结束线程
    }
}

fun main()  {
    print("Thread-Test:\n")

    val actor = Actor()
    actor.start()
    actor.postTask { print("First task!\n") }
    Thread.sleep(1000)
    actor.postTask { print("second task!\n") }

    Thread.sleep(5000)

    actor.stop()
    Thread.sleep(1000)
}
```

不含阻塞调用的线程如何响应 `interrupt`。
```kotlin
package com.uiapp.render

import java.util.concurrent.LinkedBlockingQueue

class Actor {
    var actorThread: Thread

    init {
        // 创建一个线程
        actorThread =
            Thread {
                while (!Thread.currentThread().isInterrupted) {  // 需要在这里检测线程是否被设置 interrupt 状态
                    // do nothing
                }
            }
    }

    fun start()  {
        actorThread.start() // 线程启动
    }

    fun stop()  {
        actorThread.interrupt() // 结束线程
    }
}

fun main()  {
    print("Thread-Test:\n")

    val actor = Actor()
    actor.start()
    actor.stop()
}
```


##### 线程池

线程池免去我们手动创建 Thread 的过程，同时也可以提高线程资源的利用率。

```kotlin
package com.uiapp.render

import java.util.concurrent.Executors

fun main() {
    print("ThreadPool Test:\n")
    val executor = Executors.newFixedThreadPool(2)

    executor.submit { println("Task 1 executed") }
    executor.submit { println("Task 2 executed") }
    // 这里也必须检测状态，否则整个 JVM 会卡在这个线程执行完成后才能退出
    executor.submit { while (!Thread.currentThread().isInterrupted) {} }

    // 停止提交任务
    executor.shutdown()

    // 强制停止任务，对所有的线程发送 interrupt
    executor.shutdownNow()
}

```

##### thread 语法糖

thread 语法糖没有什么特殊的地方，依旧会返回一个 `Thread` 对象，对于 `interrupt` 的处理行为也和 `Thread` 一致。

下面额外展示了一个自定义类加载器的例子。

```kotlin
fun main() {
    var jarFile = File("PATH OF com.lion.library.jar")
    var customClassLoader = URLClassLoader(arrayOf(jarFile.toURI().toURL()))

    var t =
        thread(contextClassLoader = customClassLoader) {
            val pluginClass = Class.forName("com.lion.library.Main", true, Thread.currentThread().contextClassLoader)
            val method = pluginClass.getDeclaredMethod("sayHello")
            val instance = pluginClass.getDeclaredConstructor().newInstance()
            println("Loaded plugin: $instance")
            method.invoke(instance)
        }

    t.interrupt()
}

```

#####  Handler 机制

在 Android 中，每一个线程都有一个 `Looper`，其是一个系统内置的线程处理策略，其可以以死循环的方式运行，并不断响应其余线程向其发送的事件。但是默认是不初始化的状态，为什么呢？因为我们大多数线程都是一次性逻辑，用来异步执行一个操作，操作完成后就退出，所以默认不会维持一个比较重的 `Looper` 对象。

1. 如何使用？

- 创建一个 `Handler` 绑定在一个 `Looper`。
- `Handler` 中实现一些消息的回调方法。
- 通过 `Handler` 发送消息。这个消息会发送到对应的 `Looper` 中。
- 收到消息的 `Looper` 会在自己所在的线程中调用 `callback`。

<img src="android/interview/resources/a_4.png" style="width:30%">

2. sendMessage

```kotlin
var mThread =
    thread {
        Looper.prepare() // 初始化 Looper
        mBackgroundHandler =
            object : Handler(Looper.myLooper()!!) {
                override fun handleMessage(msg: Message) {
                    when (msg.what) {
                        1 -> {
                            handler.sendMessage(
                                Message.obtain().apply {
                                    what = 1
                                    obj = "Message from background 1: ${msg.obj}"
                                },
                            )
                        }

                        2 -> {
                            handler.sendMessage(
                                Message.obtain().apply {
                                    what = 2
                                    obj = "Message from background 2: ${msg.obj}"
                                },
                            )
                        }

                        else -> {
                            handler.sendMessage(
                                Message.obtain().apply {
                                    what = 3
                                    obj = "Message from background unknown: ${msg.obj}"
                                },
                            )
                        }
                    }
                }
            }

        Looper.loop() // Looper 进入循环
    }

    // 其余线程

val message = Message()
message.obj = "Byte"
message.what = 2
mBackgroundHandler.sendMessage(message)
```

3. 如何结束一个带有 `Looper` 的线程

上文曾经提到过，我们想要对一个无限循环的线程进行终结，就需要对其发送 `interrupt` 信号 或者在初始化的时候就设置成 `damon`。 对于 `Looper` 来说本质也是一个死循环，但是和其余的不同的的地方在于，`Looper` 自身会捕获`interrupt` 信号并进行忽略处理，这导致我们发送 `interrupt` 信号不能达到预期的目的。针对于此，`Looper` 提供了更好的办法来进行退出。

```kotlin
// quit: 已开始的任务会继续执行完，但未处理的消息会被丢弃
mBackgroundHandler.looper.quit()

// 同样不中断正在执行的任务，但会保留已到执行时间的消息，仅丢弃未调度的延迟消息。
mBackgroundHandler.looper.quitSafely()
```


### BroadcastReceiver

#### 实现一个自己的 Receiver

```kotlin
class TimerReceiver : BroadcastReceiver() {
    override fun onReceive(
        context: Context?,
        intent: Intent?,
    ) {
        Toast.makeText(context, LionConstants.LION_TAG + ": TimerReceiver", Toast.LENGTH_LONG).show()
    }
}
```

#### 动态注册与静态注册

所有的 `receiver` 在使用的时候都需要注册。

##### 动态注册

```kotlin
val timeReceiver = TimerReceiver()
val intent = IntentFilter("android.intent.action.TIME_TICK")
registerReceiver(timeReceiver, intent)

// 非系统 action，需要在 register 的时候，注明 Context.RECEIVER_NOT_EXPORTED 或者 Context.RECEIVER_EXPORTED，表明是不是其他 App 可以对其发送广播。
val intent2 = IntentFilter("LION.CUSTOM_IMPLICIT_BROADCAST")
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
    registerReceiver(ImplicitReceiver(), intent2, Context.RECEIVER_NOT_EXPORTED)
}else{
    registerReceiver(ImplicitReceiver(), intent2)
}
```

##### 静态注册

```xml
<receiver android:name=".broadcast.ExplicitReceiver"
    android:enabled="true"
    android:exported="true"> // exported : true 允许其他应用发送广播给这个 receiver，为false 的话，发送的广播必须指定包名以表明是应用内广播。
    <intent-filter android:priority="100"> // 优先级，越大级别越高
        <action android:name="LION.CUSTOM_EXPLICIT_BROADCAST"/> // action，接收广播的名字
    </intent-filter>
</receiver>

<receiver android:name=".broadcast.ExplicitSecondReceiver"
    android:enabled="true"
    android:exported="true">
    <intent-filter android:priority="10">
        <action android:name="LION.CUSTOM_EXPLICIT_BROADCAST"/>
    </intent-filter>
</receiver>
```

#### 广播类型

<img src="android/interview/resources/a_5.png" style="width:70%">

##### 显式广播

发送时指定对应的 Receiver class 的就是显式广播，动态注册和静态注册的 receiver 都可以接收显式广播。

```kotlin
val intent = Intent(this, ExplicitReceiver::class.java)
sendBroadcast(intent)
```

##### 隐式广播

除了显式广播外的都是隐式广播。存在下面几个需要注意的点：
1. 除了系统的隐式广播外，静态注册的 receiver 不能接收隐式广播。
2. 静态注册的 receiver 可以接收应用内的隐式广播。
3. 动态注册的 receiver 可以接收任意来源的隐式广播。

```kotlin
// 发送 action 为 LION.CUSTOM_IMPLICIT_BROADCAST 的隐式广播
val intent = Intent("LION.CUSTOM_IMPLICIT_BROADCAST")
// 指定packagename，说明是一个应用内的广播
intent.setPackage("com.uiapp.lion")
sendBroadcast(intent)
```

#### 发送有序广播

可以使用 `sendOrderedBroadcast` 来发送有序广播，将会按照优先级来按序被 `receiver` 接收。

```kotlin
val intent = Intent("LION.CUSTOM_EXPLICIT_BROADCAST")
intent.setPackage("com.uiapp.lion")
sendOrderedBroadcast(intent, null)
```

`receiver` 中可以使用 `abortBroadcast()` 来中断消息的进一步传递。

### ContentProvider

ContentProvider主要用于在不同的应用程序之间实现数据共享的功能，它提供了一套完整的机制，允许一个程序访问另一个程序中的数据，同时还能保证被访问数据的安全性。目前，使用ContentProvider是Android实现跨程序共享数据的标准方式。

#### 动态权限申请

在获取一些系统危险权限的时候，我们不仅要在 xml 中声明权限，还要进行动态权限获取。例如获取联系人列表，进行电话呼叫。

1. XML 中注册权限

```xml
<uses-permission android:name="android.permission.CALL_PHONE" />
```

2. 代码中进行运行期动态获取, 依据获取结果执行对应的风险代码

<img src="android/interview/resources/a_6.png" style="width:20%">

```kotlin
class CallPhoneActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_callphone)
        findViewById<Button>(R.id.call).setOnClickListener {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CALL_PHONE), 1)
            } else {
                call()
            }
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String?>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        when (requestCode) {
            1 -> {
                if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED)
                    {
                        call()
                    } else {
                    Toast.makeText(this, "You denied the permission", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun call()  {
        try {
            // 使用隐式 Intent 访问对应的拨打电话的 activity
            val intent = Intent(Intent.ACTION_CALL)
            intent.data = Uri.parse("tel:564949")
            startActivity(intent)
        } catch (e: SecurityException) {
            e.printStackTrace()
        }
    }
}

```

#### 系统 ContentProvider

我们可以获取到任何提供了 ContentProvider APP 中的数据。ContentProvider 暴露出去的服务类似于一个数据库，我们可以对数据进行增删改查等操作。下面我们以读取系统联系人为例进行展示。

1. 读取联系人是一个危险权限，我们需要进行动态权限获取。同时也需要在 XML 中静态添加权限。

```xml
<uses-permission android:name="android.permission.READ_CONTACTS" />
```

2. 使用 `contentResolver` 获取对应的数据表。需要注意到是，你的 `Activity` 必须继承 `AppCompatActivity` 才会有这个成员。

```kotlin
class CallPhoneActivity : AppCompatActivity() {
    private val contactsList = ArrayList<String>()
    private lateinit var adapter: ArrayAdapter<String>

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_callphone)

        adapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, contactsList)

        findViewById<ListView>(R.id.contact_list).adapter = adapter

        findViewById<Button>(R.id.contact).setOnClickListener {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.READ_CONTACTS), 2)
            } else {
                read()
            }
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String?>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        when (requestCode) {
            2 -> {
                if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                    read()
                } else {
                    Toast.makeText(this, "You denied the permission", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun read() {
        val uri = Uri.parse("content://com.android.contacts/data/phones")
        val cursor = contentResolver.query(uri, null, null, null, null)
        while (cursor?.moveToNext() == true) {
            var index = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val name = cursor.getString(index)
            cursor.columnNames
            index = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            val number = cursor.getString(index)
            contactsList.add("$name:$number")
        }
        adapter.notifyDataSetChanged()
        cursor?.close()
    }
}

```

#### 自定义 ContentProvider

##### 实现自己的 ContentProvider

1. 定义自己的 ContentProvider
下面是几个需要注意的点：
- `authority`: 可以理解成一个 ContentProvider 的定位符，其余应用需要通过 `content://$authority/tableName` 的 uri 来找到对应的 ContentProvider

- ContentProvider 是一个数据通信类，本身没有数据存储能力。我们的数据都是借助于其他模块进行存储。例如使用 SQLite 或者文件。


```kotlin
class LionContentProvider : ContentProvider() {
    private val bookDir = 0
    private val bookItem = 1
    private val authority = "com.uiapp.lion.content.provider"
    private var dbHelper: LionDataBaseHelper? = null

    private val uriMatcher by lazy {
        val matcher = UriMatcher(UriMatcher.NO_MATCH)
        matcher.addURI(authority, "english", bookDir)
        matcher.addURI(authority, "english/#", bookItem)
        matcher
    }

    /*
     *   初始化ContentProvider的时候调用。通常会在这里完成对数据库的创建和升级等操作，
     *   返回true表示ContentProvider初始化成功，返回false则表示失败
     */
    override fun onCreate() =
        context?.let {
            dbHelper = LionDataBaseHelper(it, "lion.db", 2)
            true
        } ?: false

    override fun query(
        uri: Uri,
        projection: Array<out String>?,
        selection: String?,
        selectionArgs: Array<out String>?,
        sortOrder: String?,
    ) = dbHelper?.let {
        val db = it.readableDatabase
        val cursor =
            when (uriMatcher.match(uri)) {
                bookDir -> db.query("english", projection, selection, selectionArgs, null, null, sortOrder)
                bookItem -> {
                    val bookId = uri.pathSegments[1]
                    db.query("english", projection, "id = ?", arrayOf(bookId), null, null, sortOrder)
                }
                else -> null
            }
        cursor
    }

    override fun getType(uri: Uri) =
        when (uriMatcher.match(uri)) {
            bookDir -> "vnd.android.cursor.dir/vnd.com.uiapp.lion.content.provider.english"
            bookItem -> "vnd.android.cursor.item/vnd.com.uiapp.lion.content.provider.english"
            else -> null
        }

    override fun insert(
        uri: Uri,
        values: ContentValues?,
    ) = dbHelper?.let {
        val db = it.writableDatabase
        val uriReturn =
            when (uriMatcher.match(uri)) {
                bookDir, bookItem -> {
                    val newBookId = db.insert("english", null, values)
                    Uri.parse("content://$authority/english/$newBookId")
                }
                else -> null
            }
        uriReturn
    }

    override fun delete(
        uri: Uri,
        selection: String?,
        selectionArgs: Array<out String>?,
    ) = dbHelper?.let {
        val db = it.writableDatabase
        val deletedRows =
            when (uriMatcher.match(uri)) {
                bookDir -> db.delete("english", selection, selectionArgs)
                bookItem -> {
                    val bookId = uri.pathSegments[1]
                    db.delete("english", "id = ?", arrayOf(bookId))
                }
                else -> 0
            }
        deletedRows
    } ?: 0

    override fun update(
        uri: Uri,
        values: ContentValues?,
        selection: String?,
        selectionArgs: Array<out String>?,
    ) = dbHelper?.let {
        val db = it.writableDatabase
        val updateRows =
            when (uriMatcher.match(uri)) {
                bookDir -> db.update("english", values, selection, selectionArgs)
                bookItem -> {
                    val bookId = uri.pathSegments[1]
                    db.update("english", values, "id = ?", arrayOf(bookId))
                }
                else -> 0
            }
        updateRows
    } ?: 0
}
```

2. 注册自己的 ContentProvider.

```xml
<provider
    // authorities 对应着刚才自定义 ContentProvider 的 authority
    android:authorities="com.uiapp.lion.content.provider"
    // 自定义类的包路径
    android:name=".content.LionContentProvider"
    // 是否开启
    android:enabled="true"
    // 是否允许被其他 APP 访问
    android:exported="true"
    android:grantUriPermissions="true"/>
```

3. 设置类可见性

往往来说注册好自己的 ContentProvider 后，其余 APP 就可以使用了。但是在 API 版本大于11后，Android整了一个类可见性的机制。即除了一些系统核心应用外，其余的应用会默认对你的应用进行屏蔽。所以你要是想访问其他应用，需要进行一下配置。
如果不配置，此时你的应用假如想读取另外一个应用的 ContentProvider 的时候，会出现 ”Failed to find provider info for 'ContentProvider'” 的报错。
所以我们要主动的 queries 另外一个 application package name
> https://developer.android.google.cn/training/package-visibility/declaring?hl=en

```xml
<queries>
    <package android:name="com.uiapp.lion" />
</queries>
```
##### 增删改查

```kotlin
findViewById<Button>(R.id.find).setOnClickListener {
    val uri = Uri.parse("content://com.uiapp.lion.content.provider/english")
    bookList.clear()
    contentResolver.query(uri, null, null, null, null)?.apply {
        while (moveToNext()) {
            var index = getColumnIndex("author")
            val author = getString(index)
            index = getColumnIndex("name")
            val name = getString(index)
            index = getColumnIndex("price")
            val price = getFloat(index)
            index = getColumnIndex("pages")
            val pages = getInt(index)
            bookList.add("$name:$author\n$price:$pages")
        }
        close()
    }
    adapter.notifyDataSetChanged()
}

findViewById<Button>(R.id.delete).setOnClickListener {
    val uri = Uri.parse("content://com.uiapp.lion.content.provider/english")
    contentResolver.delete(uri, "name = ?", arrayOf("NewBee"))
}

findViewById<Button>(R.id.add).setOnClickListener {
    val uri = Uri.parse("content://com.uiapp.lion.content.provider/english")
    val values = contentValuesOf("name" to "NewBee", "author" to "Mike", "price" to 12.3, "pages" to 250)
    contentResolver.insert(uri, values)
}

findViewById<Button>(R.id.change).setOnClickListener {
    val uri = Uri.parse("content://com.uiapp.lion.content.provider/english")
    val values = contentValuesOf("name" to "OldBee")
    contentResolver.update(uri, values, "name = ?", arrayOf("NewBee"))
}
```

---

## 布局及其常用属性

### 常用的几种布局

#### 线性布局

线性布局中，所有的 UI 按照水平或者垂直的方向按序排列。

<img src="android/interview/resources/a_8.png" style="width:20%">

#### 相对布局

相对布局默认会将所有的子视图堆叠在左上方展示，你可以使用一系列的操作来调整子视图之间以及子视图与父视图之间的位置关系。

<img src="android/interview/resources/a_9.png" style="width:10%">

#### 帧布局

帧布局，将所有的元素按照声明是从上到下的顺序叠加显示。类似于图层的概念。

#### 网格布局

GridLayout 是 Android 中的一种布局管理器，用于在网格形式的布局中排列子视图。通过 GridLayout，可以将子视图按行和列的方式排列在屏幕上，类似于表格布局。每个子视图可以占据一个或多个网格单元格，从而实现灵活的布局。

<img src="android/interview/resources/a_10.png" style="width:50%">

```xml
        <GridLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:rowCount="3"
            android:columnCount="2"
            android:background="@drawable/black_shape">
                <Button
                    android:layout_width="100dp"
                    android:layout_height="20dp"
                    android:text="Button 1"
                    android:background="@color/green"
                    android:layout_row="0"
                    android:layout_column="0"
                    />

                <Button
                    android:layout_width="100dp"
                    android:layout_height="20dp"
                    android:text="Button 2"
                    android:background="@color/red"
                    android:layout_row="0"
                    android:layout_column="1"
                    />
                <Button
                    android:layout_width="100dp"
                    android:layout_height="20dp"
                    android:text="Button 3"
                    android:background="@color/red"
                    android:layout_row="1"
                    android:layout_column="0"
                    />
                <Button
                    android:layout_width="100dp"
                    android:layout_height="20dp"
                    android:text="Button 4"
                    android:background="@color/green"
                    android:layout_row="1"
                    android:layout_column="1"
                    />

                <Button
                    android:layout_width="200dp"
                    android:layout_height="20dp"
                    android:text="Button 5"
                    android:background="@color/green"
                    android:layout_row="2"
                    android:layout_column="0"
                    android:layout_columnSpan="2"
                    />
        </GridLayout>
```

#### 约束布局

<img src="android/interview/resources/a_11.png" style="width:50%">

它允许开发者通过设置视图之间的约束关系来定义视图的位置和大小，从而实现灵活性和性能的最佳平衡。

--- 

## 自定义 View 及 ViewGroup

### View 的 Measure 、Layout 、Draw 流程分析

[流程分析](android/interview/view-mld/)

### 继承 View

#### 什么时候需要继承 View

1. 当你需要创建视觉上完全独特、无法通过组合现有组件实现的视图时。
2. 当你需要像素级的精确控制绘制过程时。
3. 性能优化要求极高，且现有组件组合无法满足性能目标时。

#### 特点

1. 最大灵活性: 你可以绘制任何你能想象到的视觉元素。
2. 最高控制权: 完全掌控视图的尺寸测量(onMeasure)、布局(onLayout - 对于单个View通常不需要)、绘制(onDraw)和触摸事件处理(onTouchEvent)。
3. 最高复杂度: 需要自己处理所有细节，代码量通常较大。
4. 性能敏感: 高效的 onDraw 实现至关重要，避免过度绘制和不必要的对象创建。

#### 实现步骤

1. 设置自定义 View 的属性

我们自定义 View 可能和 Android 原生 View 一样，具有一些特有的属性，例如我想实现一个圆形的 View，它可能需要提供属性来让用户指定圆心和半径。
这些属性需要我们在 `res/values/attrs.xml` 中实现。

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <declare-styleable name="Circle">
        <attr name="circleColor" format="color" />
        <attr name="circleRadius" format="dimension" />
        <attr name="strokeWidth" format="dimension" />
        <attr name="strokeColor" format="color" />
    </declare-styleable>
</resources>
```

2. 编写对应的 View 类

编写的过程需要做几个关键点：
- 自定义属性解析
- onMeasure 方法编写、
- onDraw 方法编写。
- 在合适的地方触发布局和重绘制。
- 对于 View 因为没有子节点，就不需要关注 onLayout 了。

```kotlin
class Circle(ctx: Context, attrs: AttributeSet? = null, defStyleAttr: Int = 0) : View(ctx, attrs, defStyleAttr) {
    // 定义两个构造函数，第一个用于在代码重创建 Circle 对象调用。第二个用于在 xml 中引用
    constructor(ctx: Context) : this(ctx, null, 0) {}
    constructor(ctx: Context, attr: AttributeSet) : this(ctx, attr, 0) {}

    // 创建一些内部的属性
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val strokePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE }

    private var circleColor: Int = Color.RED
    private var strokeColor: Int = Color.BLACK
    private val Float.dp: Float
        get() = this * resources.displayMetrics.density
    private var circleRadius: Float = 50f.dp
    private var strokeWidth: Float = 0f

    // 在初始化块中，解析从 xml 中传入的属性
    init {
        context.obtainStyledAttributes(attrs, R.styleable.Circle).apply {
            try {
                circleColor = getColor(R.styleable.Circle_circleColor, Color.RED)
                strokeColor = getColor(R.styleable.Circle_strokeColor, Color.BLACK)
                circleRadius = getDimension(R.styleable.Circle_circleRadius, 50f.dp)
                strokeWidth = getDimension(R.styleable.Circle_strokeWidth, 0f)
            } finally {
                recycle()
            }
        }
        fillPaint.color = circleColor
        strokePaint.color = strokeColor
        strokePaint.strokeWidth = strokeWidth
    }

    // 重写 onMeasure 方法，完成自己的尺寸计算
    override fun onMeasure(
        widthMeasureSpec: Int,
        heightMeasureSpec: Int,
    ) {
        val desiredSize = (2 * circleRadius + strokeWidth * 2).toInt()
        val desiredWidth = desiredSize + paddingLeft + paddingRight
        val desiredHeight = desiredSize + paddingTop + paddingBottom

        // resolveSize 是在考虑父组件约束条件下的尺寸，相比于不考虑约束设置尺寸，拥有更好的性能和稳定性。
        val measuredWidth = resolveSize(desiredWidth, widthMeasureSpec)
        val measuredHeight = resolveSize(desiredHeight, heightMeasureSpec)

        val minSize = Math.max(1, Math.min(measuredWidth, measuredHeight))

        // 最后将我们所需的尺寸设置
        setMeasuredDimension(minSize, minSize)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)

        val centerX = width / 2f
        val centerY = height / 2f

        val maxRadius = (Math.min(width, height) - paddingLeft - paddingRight) / 2f
        val actualRadius = circleRadius.coerceAtMost(maxRadius)

        // 画圆
        canvas.drawCircle(centerX, centerY, actualRadius, fillPaint)

        // 画描边
        if (strokeWidth > 0) {
            canvas.drawCircle(centerX, centerY, actualRadius, strokePaint)
        }
    }

    // 提供对外设置颜色的接口，设置了颜色后，调用 invalidate 触发重绘。
    fun setCircleColor(color: Int) {
        circleColor = color
        fillPaint.color = color
        invalidate()
    }

    // 描边颜色变化后也需要触发重绘。
    fun setStrokeColor(color: Int) {
        strokeColor = color
        strokePaint.color = color
        invalidate()
    }

    // 设置圆心，因为涉及到位置的变化，我们需要触发重新排版，同时触发重绘。
    fun setCircleRadius(radius: Float) {
        circleRadius = radius
        requestLayout()
        invalidate()
    }

    // 设置边框宽度，因为涉及到位置的变化，我们需要触发重新排版，同时触发重绘。
    fun setStrokeWidth(width: Float) {
        strokeWidth = width
        strokePaint.strokeWidth = width
        requestLayout()
        invalidate()
    }
}
```

3. 在 XML 中引入 自定义 View

在 XML 中需要声明 app scope,以引入我们的自定义属性。

```xml
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
    <com.uiapp.uitest.Circle
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        app:circleColor="#4CAF50"
        app:circleRadius="40dp"
        android:padding="10dp"/>
</LinearLayout>
```

#### 为什么需要使用 resolveSize？

> 这段话来自于 deepseek 的解释，我觉得非常完整，就直接摘抄了，感谢 deepseek

这是一个非常核心的问题，触及到 Android 视图系统 onMeasure 阶段的本质：协商。直接设置 size（你计算出来的理想尺寸）而不考虑父布局传递进来的 MeasureSpec 约束，是导致布局错乱、性能低下甚至崩溃的常见原因。resolveSize() 或 resolveSizeAndState() 的作用就是帮你在这个协商过程中，根据父布局的约束 (MeasureSpec) 和你自身的需求，计算出最终合规且合理的尺寸。

为什么不能直接设置 size？需要理解 MeasureSpec 和协商过程：

1. MeasureSpec 是父布局的指令：
当父布局（一个 ViewGroup）测量其子视图时，它会为每个子视图生成一个 MeasureSpec（一个32位整数，封装了尺寸模式和尺寸值）。
MeasureSpec 包含两种信息：
- 模式 (Mode):
    - EXACTLY (精确模式)：父布局已经明确决定了子视图的大小。子视图必须使用这个尺寸。通常对应于 layout_width/layout_height 设置为具体数值 (dp) 或 match_parent。
    - AT_MOST (最大模式)：父布局给出了一个子视图可以使用的最大尺寸。子视图不能超过这个尺寸，但可以更小。通常对应于 layout_width/layout_height 设置为 wrap_content。
    - UNSPECIFIED (未指定模式)：父布局对子视图的大小没有任何限制。子视图可以根据自己的内容需求自由决定大小。这种情况相对少见，通常出现在 ScrollView 测量其子视图高度、AdapterView 测量 item 视图或在自定义布局的某些测量阶段。
- 尺寸值 (Size): 与模式对应的尺寸数值（对于 EXACTLY 是精确值，对于 AT_MOST 是最大值）。

2. onMeasure 的责任：响应父布局的约束
自定义视图的 onMeasure(int widthMeasureSpec, int heightMeasureSpec) 方法的核心职责是：
- 理解约束： 解析传入的 widthMeasureSpec 和 heightMeasureSpec，明白父布局对你的宽度和高度有什么要求（是精确值？不能超过某个最大值？还是随便你？）。
- 计算自身需求： 根据你的视图内容（文本、图片、绘制逻辑）、内边距 (padding) 以及任何自定义逻辑，计算出一个你希望拥有的理想尺寸 (desiredSize)。
- 协商最终尺寸： 将你的 desiredSize 与父布局的 MeasureSpec 进行协商，确定一个既满足父布局约束，又尽可能符合你自身需求的最终尺寸 (finalSize)。
- 报告结果： 调用 setMeasuredDimension(finalWidth, finalHeight) 将协商后的最终尺寸报告给父布局系统。

3. resolveSize() / resolveSizeAndState() 的作用：自动化协商
这些辅助方法封装了上述协商过程（步骤3）的标准逻辑。你提供你的 desiredSize 和父布局的 MeasureSpec，它们根据 MeasureSpec 的模式智能地计算出 finalSize。
协商规则：
- MeasureSpec.EXACTLY： 父说了算！直接返回 MeasureSpec 中的 size。忽略你的 desiredSize。
- MeasureSpec.AT_MOST： 父给了一个上限。你的 desiredSize 不能超过这个上限。返回 min(desiredSize, MeasureSpec.size)。
- MeasureSpec.UNSPECIFIED： 父没限制。你可以按自己的意愿来。返回 desiredSize。
resolveSizeAndState() 更进一步：它除了返回尺寸，还会返回一个状态标志（如 MEASURED_STATE_TOO_SMALL），告诉父布局“我计算的最小尺寸比 AT_MOST 给我的最大值还大，如果你能给我更多空间，我会表现得更好”。父布局（如果支持）可能利用这个信息进行二次测量。

4. 不使用 resolveSize() 直接设置 size 的后果：
- 违反 EXACTLY 约束： 如果父布局要求你必须是特定大小（比如 match_parent 或固定 100dp），你直接返回了自己的 desiredSize（比如 200dp），视图会显示为 200dp。这会破坏父布局（如 LinearLayout 权重分配、ConstraintLayout 的约束链）的布局计算，导致其他视图位置错乱或父布局自身尺寸计算错误。视图可能会重叠、超出屏幕或布局完全崩溃。
- 违反 AT_MOST 约束： 如果父布局要求你不能超过某个尺寸（比如因为它是 wrap_content 的容器），你直接返回了一个更大的 desiredSize，视图会显示为超出父容器边界。内容被裁剪、父容器出现不必要的滚动条，或者完全破坏父容器的布局意图（例如一个 wrap_content 的 LinearLayout 变得异常巨大）。
- 忽略 UNSPECIFIED 的机会： 虽然直接设置 size 在 UNSPECIFIED 下是安全的（因为规则就是你想多大就多大），但使用 resolveSize() 保持了代码的一致性，清晰地表达了“我考虑了约束”。
- 代码健壮性和可维护性差： 手动实现上述 if-else 逻辑来判断 MeasureSpec 模式并计算最终尺寸是繁琐且容易出错的。resolveSize() 提供了标准、可靠且易于理解的实现。

#### requestLayout 和 invalidate 机制

##### invalidate 请求重绘

```java
// 标记整个视图为无效，需要重绘
invalidate();

// 指定需要重绘的矩形区域（优化性能）
invalidate(left, top, right, bottom);
```

1. 作用

- 标记视图的内容已失效，需要重新绘制
- 只触发视图的 onDraw(Canvas) 方法
- 不会触发测量(onMeasure)或布局(onLayout)

2. 适用场景

- 视图内容变化但是尺寸没有变化

##### requestLayout 请求重新布局

1. 作用
- 声明视图的尺寸或位置已失效
- 触发完整的视图树更新流程：
    - onMeasure() → 重新计算尺寸
    - onLayout() → 重新分配位置
    - onDraw() → 最终重绘（如果需要）

##### 那既然 requestLayout 也会触发整个管线，那我为啥还要在 requestLayout 后在调用 invalidate呢？

就像这个函数一样，按照上面的分析，requestLayout 会触发完整的流程，为什么还要进行 invalidate 调用。

```kotlin
fun setStrokeWidth(width: Float) {
    strokeWidth = width
    strokePaint.strokeWidth = width
    requestLayout()
    invalidate()
}
```

核心原因：requestLayout() 不保证触发 onDraw()
这是最关键的区别：requestLayout() 会触发 onMeasure() 和 onLayout()，但不一定触发 onDraw()！是否重绘取决于视图系统的内部优化机制。

什么时候 requestLayout 会触发 onDraw 呢？
1. 如果视图的位置发生变化，系统会自动触发 onDraw。
2. 如果用户手动的调用了 invalidate 标记视图为 dirty，那就会触发。
3. 如果视图只是绘制状态变化，例如背景色变化，而此时没有尺寸变化，或者 dirty，是不会重绘的。

<img src="android/interview/resources/a_12.png" style="width:30%">

##### 会存在双重绘制吗？

这段代码调用了 requestLayout,此时视图尺寸发生变化，会触发 onDraw，后续 invalidate 又触发一次 onDraw，这样重复绘制符合预期吗，
```kotlin
fun setCircleRadius(radius: Float) {
    circleRadius = radius
    requestLayout()
    invalidate()
}
```

首先，requestLayout 和 invalidate 都是提交请求而不立即执行的操作，他们提交的请求会在 VSync 到来后被做处理。也就是说大多数情况下，这两次对于绘制的请求会被合并成一次真正的绘制操作。

例如下面的伪代码，当区域更改了，会触发 draw，当 inavlidate 被设置了，会触发 draw。

第一种情况：发起 requestLayout后，VSync 到来，此时 invalidate 还没有发起，但是因为尺寸变化，触发一次 draw，结束本次 VSync 后，invalidate 发起，在第二次 VSync 后，因为检测到设置了 invalidate，又重新绘制了一次。

第二种情况：requestLayout 和 invalidate 在同一帧内提交，那 VSync 到来后，只会触发一次 draw。

```kotlin
if(area_changed || invalidate){
    view.draw(canvas)
}
```
### 继承 ViewGroup

#### 什么时候需要继承 ViewGroup

1. 我们想要实现自定义的布局形式。例如环形布局。
2. 我们想组合 View，以便于复用。例如给 ViewGroup 挂接图片和文字组成一个图片介绍组件。


#### 组合View

1. 依然可以定义自己的属性

```xml
<declare-styleable name="CardView">
    <attr name="imageSrc" format="reference" />
</declare-styleable>
```

2. 实现自己的类，继承 ViewGroup

下面实现了一个布局，这个布局中，上方是一个图片，中部是图片介绍，下方有个按钮，点击按钮可以关闭/显示图片介绍。其中图片和按钮都需要居中。

<img src="android/interview/resources/a_13.png" style="width:30%">

- 重写 onMeasure
- 重写 onLayout
- 一般不需要重写 onDraw

```kotlin
class CardView
    @JvmOverloads
    constructor(
        context: Context,
        attrs: AttributeSet? = null,
        defStyleAttr: Int = 0,
    ) : ViewGroup(context, attrs, defStyleAttr) {
        private val imageView: ImageView
        private val descriptionView: TextView
        private val actionButton: Button

        private var isDescriptionVisible = true
        private var imageSelect = false

        init {
            // 设置背景和边距
            background = ContextCompat.getDrawable(context, R.drawable.card_background)
            setPadding(resources.getDimensionPixelSize(R.dimen.card_padding))

            // 创建图片视图
            imageView =
                ImageView(context).apply {
                    id = R.id.card_image
                    scaleType = ImageView.ScaleType.CENTER_CROP
                    setBackgroundColor(Color.parseColor("#EEEEEE"))
                    addView(this)

                    context.obtainStyledAttributes(attrs, R.styleable.CardView).apply {
                        try {
                            val image = getResourceId(R.styleable.CardView_imageSrc, -1)
                            if (image != -1) {
                                setImageResource(image)
                            }
                        } finally {
                            recycle()
                        }
                    }
                }

            // 创建描述文本
            descriptionView =
                TextView(context).apply {
                    id = R.id.card_description
                    text = "这是一个非常有趣的自定义视图组件，包含了图片、文字介绍和交互按钮。点击下方按钮可以切换文字介绍的显示状态。"
                    setTextColor(Color.DKGRAY)
                    textSize = 16f
                    setLineSpacing(0f, 1.2f)
                    addView(this)
                }

            // 创建操作按钮
            actionButton =
                Button(context).apply {
                    id = R.id.card_button
                    text = "隐藏介绍"
                    setTextColor(Color.WHITE)
                    setBackgroundColor(Color.parseColor("#4CAF50"))
                    setPadding(resources.getDimensionPixelSize(R.dimen.button_padding))
                    addView(this)

                    // 设置按钮点击事件
                    setOnClickListener {
                        toggleDescription()
                    }
                }
        }

        // 切换描述文本的可见性
        private fun toggleDescription() {
            isDescriptionVisible = !isDescriptionVisible
            descriptionView.visibility = if (isDescriptionVisible) View.VISIBLE else View.GONE
            actionButton.text = if (isDescriptionVisible) "隐藏介绍" else "显示介绍"

            imageView.setImageResource(
                if (imageSelect) {
                    R.drawable.ic_launcher_foreground
                } else {
                    R.drawable.ic_launcher_background
                },
            )
            imageSelect = !imageSelect

            // 不需要，因为 系统 UI 属性发生变化后，会自动触发 requestLayout
            // requestLayout()
        }

        override fun onMeasure(
            widthMeasureSpec: Int,
            heightMeasureSpec: Int,
        ) {
            // 测量所有子视图, 测量子视图的时候，需要传入当前视图的宽高约束
            measureChildren(widthMeasureSpec, heightMeasureSpec)

            val widthMode = MeasureSpec.getMode(widthMeasureSpec)
            val widthSize = MeasureSpec.getSize(widthMeasureSpec)
            val heightMode = MeasureSpec.getMode(heightMeasureSpec)
            val heightSize = MeasureSpec.getSize(heightMeasureSpec)

            // 计算内容宽度（取子视图最大宽度）
            val contentWidth =
                max(
                    imageView.measuredWidth,
                    max(descriptionView.measuredWidth, actionButton.measuredWidth),
                ) + paddingLeft + paddingRight

            // 计算内容高度
            var contentHeight = paddingTop + paddingBottom
            contentHeight += imageView.measuredHeight
            if (isDescriptionVisible) {
                contentHeight += descriptionView.measuredHeight
            }
            contentHeight += actionButton.measuredHeight
            contentHeight += resources.getDimensionPixelSize(R.dimen.element_spacing) * 2

            // 确定最终尺寸
            val width =
                when (widthMode) {
                    MeasureSpec.EXACTLY -> widthSize
                    MeasureSpec.AT_MOST -> minOf(contentWidth, widthSize)
                    else -> contentWidth
                }

            val height =
                when (heightMode) {
                    MeasureSpec.EXACTLY -> heightSize
                    MeasureSpec.AT_MOST -> minOf(contentHeight, heightSize)
                    else -> contentHeight
                }

            setMeasuredDimension(width, height)
        }

        override fun onLayout(
            changed: Boolean,
            l: Int,
            t: Int,
            r: Int,
            b: Int,
        ) {
            val spacing = resources.getDimensionPixelSize(R.dimen.element_spacing)
            var currentTop = paddingTop

            val imageLeft = paddingLeft + (measuredWidth - paddingLeft - paddingRight - imageView.measuredWidth) / 2
            // 布局图片视图
            imageView.layout(
                imageLeft,
                currentTop,
                imageLeft + imageView.measuredWidth,
                currentTop + imageView.measuredHeight,
            )
            currentTop += imageView.measuredHeight + spacing

            // 布局描述文本（如果可见）
            if (isDescriptionVisible) {
                descriptionView.layout(
                    paddingLeft,
                    currentTop,
                    paddingLeft + descriptionView.measuredWidth,
                    currentTop + descriptionView.measuredHeight,
                )
                currentTop += descriptionView.measuredHeight + spacing
            }

            // 布局按钮（居中）
            val buttonLeft = paddingLeft + (measuredWidth - paddingLeft - paddingRight - actionButton.measuredWidth) / 2
            actionButton.layout(
                buttonLeft,
                currentTop,
                buttonLeft + actionButton.measuredWidth,
                currentTop + actionButton.measuredHeight,
            )
        }

        // 设置图片资源
        fun setImageResource(resId: Int) {
            imageView.setImageResource(resId)
        }

        // 设置描述文本
        fun setDescription(text: String) {
            descriptionView.text = text
            // 同样不需要
            // requestLayout()
        }

        // 设置按钮文本
        fun setButtonText(text: String) {
            actionButton.text = text
        }

        // 设置按钮点击监听
        fun setOnButtonClickListener(listener: OnClickListener) {
            actionButton.setOnClickListener {
                // 先执行自定义的点击事件
                listener.onClick(it)
                // 再执行默认的切换功能
                toggleDescription()
            }
        }
    }
```









#### 实现自定义的布局形式

我现在有如下的需求，设计一个布局，在这个布局中的子元素如果增加了 isMain 参数，那这个视图就独占容器左侧，其余视图都线性从上到下安排在容器右侧。

1. 定义属性 `isMain`

```xml
<declare-styleable name="SplitContainer_Layout">
    <attr name="isMain" format="boolean" />
</declare-styleable>
```

2. 实现自定义 ViewGroup

- 因为我们不是自定义的 View， 所以没法直接拿到我们 ViewGroup 中子元素的属性，所以没办法判断其是不是包含了 `isMain` 属性，所以我们需要重定义 ViewGroup 的 LayoutParams，对于一个 ViewGroup 来说，其所有被添加的子元素都会使用这个 ViewGroup 的三个方法来获取自己的 layoutParams。所以这里我们重定义这些方法，来得以解析子视图的属性。

```java
LayoutParams getLayoutParams(View child) {
    if (child.hasLayoutParams()) {
        // 调用 generateLayoutParams(ViewGroup.LayoutParams)
        return generateLayoutParams(child.getLayoutParams());
    } else if (从XML加载) {
        // 调用 generateLayoutParams(AttributeSet)
        return generateLayoutParams(attrs);
    } else {
        // 调用 generateDefaultLayoutParams()
        return generateDefaultLayoutParams();
    }
}
```

```kotlin
class SplitContainer(context: Context, attributeSet: AttributeSet? = null, defStyleAttr: Int = 0) :
    ViewGroup(context, attributeSet, defStyleAttr) {
    
    // 重定义 layoutParams, 得以解析子视图的属性
    class LayoutParams(
        context: Context,
        attrs: AttributeSet?,
    ) : ViewGroup.LayoutParams(context, attrs) {
        var isMain: Boolean = false

        init {
            context.obtainStyledAttributes(attrs, R.styleable.SplitContainer_Layout).apply {
                try {
                    isMain = getBoolean(R.styleable.SplitContainer_Layout_isMain, false)
                } finally {
                    recycle()
                }
            }
        }
    }

    constructor(context: Context, attributeSet: AttributeSet? = null) : this(context, attributeSet, 0) {}

    private var mainView: View? = null
    private val rightViews = mutableListOf<View>()

    // 重定义这两个方法
    override fun generateLayoutParams(attrs: AttributeSet?): ViewGroup.LayoutParams? {
        return LayoutParams(context, attrs)
    }

    override fun generateLayoutParams(p: ViewGroup.LayoutParams?): ViewGroup.LayoutParams? {
        return LayoutParams(p?.width ?: 0, p?.height ?: 0)
    }

    override fun onMeasure(
        widthMeasureSpec: Int,
        heightMeasureSpec: Int,
    ) {
        findMainView()

        val widthSize = MeasureSpec.getSize(widthMeasureSpec)
        val widthMode = MeasureSpec.getMode(widthMeasureSpec)
        val heightSize = MeasureSpec.getSize(heightMeasureSpec)
        val heightMode = MeasureSpec.getMode(heightMeasureSpec)

        var totalHeight = 0
        var maxRightHeight = 0

        val leftWidth =
            if (mainView != null) {
                widthSize / 2
            } else {
                0
            }
        val rightWidth = widthSize - leftWidth

        mainView?.let {
            val childWidthSpec = MeasureSpec.makeMeasureSpec(leftWidth, MeasureSpec.EXACTLY)
            val childHeightSpec = MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED)
            measureChild(it, childWidthSpec, childHeightSpec)
            totalHeight = max(totalHeight, it.measuredHeight)
        }

        rightViews.forEach { view ->
            val childWidthSpec = MeasureSpec.makeMeasureSpec(rightWidth, MeasureSpec.EXACTLY)
            val childHeightSpec = MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED)
            measureChild(view, childWidthSpec, childHeightSpec)

            maxRightHeight += view.measuredHeight
        }

        totalHeight = max(totalHeight, maxRightHeight)

        val finalWidth =
            when (widthMode) {
                MeasureSpec.EXACTLY -> widthSize
                else -> widthSize.coerceAtLeast(suggestedMinimumWidth)
            }

        val finalHeight =
            when (heightMode) {
                MeasureSpec.EXACTLY -> heightSize
                else -> totalHeight.coerceAtLeast(suggestedMinimumHeight)
            }

        setMeasuredDimension(finalWidth, finalHeight)
    }

    override fun onLayout(
        changed: Boolean,
        l: Int,
        t: Int,
        r: Int,
        b: Int,
    ) {
        val width = width
        val halfWidth =
            if (mainView != null) {
                width / 2
            } else {
                0
            }

        // 布局主视图（左侧居中）
        mainView?.let { view ->
            val viewHeight = view.measuredHeight
            val top = (height - viewHeight) / 2
            view.layout(0, top, halfWidth, top + viewHeight)
        }

        // 布局右侧视图（垂直排列）
        var currentTop = 0
        rightViews.forEach { view ->
            val viewHeight = view.measuredHeight
            view.layout(halfWidth, currentTop, width, currentTop + viewHeight)
            currentTop += viewHeight
        }
    }

    private fun findMainView() {
        mainView = null
        rightViews.clear()

        for (i in 0 until childCount) {
            val child = getChildAt(i)
            if (child.visibility != GONE) {
                val lp = child.layoutParams as? LayoutParams
                if (lp?.isMain == true) {
                    if (mainView == null) {
                        mainView = child
                    }
                } else {
                    rightViews.add(child)
                }
            }
        }
    }
}

```

### 继承 TextView

### 继承 LinearLayout

### 组合 View

---

## 动画

### View 动画

#### AlphaAnimation

#### ScaleAnimation

#### TranslateAnimation

#### RotateAnimation

#### AnimationSet

### 属性动画


--- 

## 数据库框架

###  文件流

### SQLite

Android 操作系统内置了 SQLite 数据库。并提供了对应的接口 `SQLiteHelper` 来进行操作。

#### 数据库存储位置

在 Android 中，应用创建的数据库存储在 `/data/data/your.app.package.name/databases/xxx.db`

我们可以将这个 db 文件导出来，利用 `database navigator` 等工具进行查看。

<img src="android/interview/resources/a_7.png" style="width:50%">

#### 数据库创建与更新

我们想创建自己的数据需要按照如下步骤。
1. 继承 `SQLiteOpenHelper` 

```kotlin
// name: 数据库名称
// version: 数据库版本
class LionDataBaseHelper(val context: Context, name: String, version: Int) : SQLiteOpenHelper(context, name, null, version) {
    private val createBoolTable =
        "create table english(" +
            "id integer primary key autoincrement," +
            "author text," +
            "price real," +
            "pages integer," +
            "name text)"

    // 如果name 指定的数据库不存在，就会调用 onCreate
    override fun onCreate(db: SQLiteDatabase?) {
        db?.execSQL(createBoolTable)
        Toast.makeText(context, "DB create success!", Toast.LENGTH_SHORT).show()
    }

    // 在构建 LionDataBaseHelper 实例的时候，如果 version 发生变化，那就会触发 onUpgrade。
    // 如果是第一次创建这个数据库，那是不会调用 onUpgrade 的。
    override fun onUpgrade(
        db: SQLiteDatabase?,
        oldVersion: Int,
        newVersion: Int,
    ) {
        db?.execSQL("drop table if exists Book")
        onCreate(db)
    }
}
```

2. 进行任意一次数据库读写操作

仅仅初始化一次 DataBase 并不会创建数据库，真正创建来自于读写操作。

```kotlin
LionDataBaseHelper(this, "lion.db", 2).writableDatabase
```

3. 想更新数据库，那就在初始化的时候，传入不同的版本，需要注意的是，对于已经存在的数据库不可以降版本更新。

#### 增删改查

1. 增加数据

```kotlin
val db = dbHelper.writableDatabase
val values =
    ContentValues().apply {
        put("name", "FirstBlood")
        put("price", 10.3)
        put("pages", index++)
        put("author", "zhangsan")
    }
db.insert("english", null, values)
```

2. 删除数据

```kotlin
val db = dbHelper.writableDatabase
db.delete("english", "pages > ?", arrayOf("0"))
```

3. 修改数据

```kotlin
val db = dbHelper.writableDatabase
val values =
    ContentValues().apply {
        put("author", "lisi")
    }
db.update("english", values, "pages > ?", arrayOf("0"))
```

4. 查询数据

```kotlin
val db = dbHelper.readableDatabase
val cursor = db.query("english", null, null, null, null, null, null)
contactsList.clear()
if (cursor.moveToFirst()) {
    do {
        var index = cursor.getColumnIndex("name")
        val name = cursor.getString(index)
        index = cursor.getColumnIndex("price")
        val price = cursor.getFloat(index)
        index = cursor.getColumnIndex("pages")
        val pages = cursor.getInt(index)
        index = cursor.getColumnIndex("author")
        val author = cursor.getString(index)
        contactsList.add("$name:$author\n$price, $pages")
    } while (cursor.moveToNext())
}
adapter.notifyDataSetChanged()
cursor.close()
```

### LitePal 数据库框架


--- 

## 网络框架

### HTTP/HTTPS 基础知识

### OkHttp 网络框架

#### 基本 GET 请求

```java
OkHttpClient client = new OkHttpClient();

Request request = new Request.Builder()
    .url("https://api.example.com/data")
    .build();

try (Response response = client.newCall(request).execute()) {
    if (!response.isSuccessful()) throw new IOException("Unexpected code " + response);
    
    String responseData = response.body().string();
    System.out.println(responseData);
}
```

#### 异步 GET 请求

```java
OkHttpClient client = new OkHttpClient();

Request request = new Request.Builder()
    .url("https://api.example.com/data")
    .build();

client.newCall(request).enqueue(new Callback() {
    @Override
    public void onFailure(Call call, IOException e) {
        e.printStackTrace();
    }

    @Override
    public void onResponse(Call call, Response response) throws IOException {
        try (ResponseBody responseBody = response.body()) {
            if (!response.isSuccessful()) throw new IOException("Unexpected code " + response);
            
            String responseData = responseBody.string();
            System.out.println(responseData);
        }
    }
});
```

#### POST 请求

1. 发送表单数据

```java
OkHttpClient client = new OkHttpClient();

RequestBody formBody = new FormBody.Builder()
    .add("username", "user123")
    .add("password", "secret")
    .build();

Request request = new Request.Builder()
    .url("https://api.example.com/login")
    .post(formBody)
    .build();

try (Response response = client.newCall(request).execute()) {
    // 处理响应
}
```

2. 发送 JSON 数据

```java
OkHttpClient client = new OkHttpClient();

String json = "{\"name\":\"John\", \"age\":30}";
RequestBody body = RequestBody.create(
    json, 
    MediaType.get("application/json; charset=utf-8")
);

Request request = new Request.Builder()
    .url("https://api.example.com/users")
    .post(body)
    .build();

try (Response response = client.newCall(request).execute()) {
    // 处理响应
}
```

3. 发送文件

```java
OkHttpClient client = new OkHttpClient();

RequestBody requestBody = new MultipartBody.Builder()
    .setType(MultipartBody.FORM)
    .addFormDataPart("title", "My File")
    .addFormDataPart("file", "file.txt",
        RequestBody.create(new File("path/to/file.txt"), 
        MediaType.get("text/plain")))
    .build();

Request request = new Request.Builder()
    .url("https://api.example.com/upload")
    .post(requestBody)
    .build();

try (Response response = client.newCall(request).execute()) {
    // 处理响应
}
```

#### 添加请求头

```java
Request request = new Request.Builder()
    .url("https://api.example.com/data")
    .header("Authorization", "Bearer token123")
    .addHeader("User-Agent", "MyApp/1.0")
    .build();
```

#### 使用 Cookie

```java
CookieJar cookieJar = new CookieJar() {
    private final HashMap<String, List<Cookie>> cookieStore = new HashMap<>();

    @Override
    public void saveFromResponse(HttpUrl url, List<Cookie> cookies) {
        cookieStore.put(url.host(), cookies);
    }

    @Override
    public List<Cookie> loadForRequest(HttpUrl url) {
        List<Cookie> cookies = cookieStore.get(url.host());
        return cookies != null ? cookies : new ArrayList<Cookie>();
    }
};

OkHttpClient client = new OkHttpClient.Builder()
    .cookieJar(cookieJar)
    .build();
```

#### 使用拦截器

```java
// 自定义拦截器
class LoggingInterceptor implements Interceptor {
    @Override
    public Response intercept(Chain chain) throws IOException {
        Request request = chain.request();
        
        long t1 = System.nanoTime();
        System.out.println(String.format("Sending request %s on %s%n%s",
            request.url(), chain.connection(), request.headers()));

        Response response = chain.proceed(request);
        
        long t2 = System.nanoTime();
        System.out.println(String.format("Received response for %s in %.1fms%n%s",
            response.request().url(), (t2 - t1) / 1e6d, response.headers()));
            
        return response;
    }
}

// 使用拦截器
OkHttpClient client = new OkHttpClient.Builder()
    .addInterceptor(new LoggingInterceptor())
    .build();
```

#### WebSocket

```java
OkHttpClient client = new OkHttpClient();

Request request = new Request.Builder()
    .url("wss://echo.websocket.org")
    .build();

WebSocket webSocket = client.newWebSocket(request, new WebSocketListener() {
    @Override
    public void onOpen(WebSocket webSocket, Response response) {
        System.out.println("WebSocket opened");
        webSocket.send("Hello WebSocket!");
    }

    @Override
    public void onMessage(WebSocket webSocket, String text) {
        System.out.println("Received message: " + text);
    }

    @Override
    public void onClosed(WebSocket webSocket, int code, String reason) {
        System.out.println("WebSocket closed");
    }

    @Override
    public void onFailure(WebSocket webSocket, Throwable t, Response response) {
        t.printStackTrace();
    }
});

// 关闭WebSocket
// webSocket.close(1000, "Goodbye!");
```

### Retrofit 网络框架

Retrofit 是一个高层的网络客户端工具，底层可以基于 OkHttp 以及其他的网络库完成网络请求。


--- 

## RxJava

### RxJava 的优点

### RxJava 原理

### RxJava 使用

### 操作符

--- 


## 事件分发机制

### 触摸事件分发

### Activity 事件分发

### ViewGroup 与 View 事件分发

--- 


## MVC、MVP、MVVM

[MVC、MVP、MVVM](android/interview/mvc/)

--- 

## 图片加载框架

### Glide

### ImageLoader

### Pocasso


--- 

## 性能优化

### 性能优化

#### 布局优化

#### 绘制优化

#### 内存优化

#### 包优化

#### BitMap 优化


---

## 跨进程通信

### 进程与线程

### Android 的 IPC


--- 

## Java 语言概述


