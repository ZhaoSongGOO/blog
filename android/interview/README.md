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

### 自定义 View

### 自定义 ViewGroup

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

### Retrofit 网络框架


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

### MVC

### MVP

### MVVM


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


