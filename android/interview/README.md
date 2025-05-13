# Android 面试知识点

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

#### 服务类型

#### Handler 机制

### BroadcastReceiver

#### 动态注册与静态注册

#### 广播类型

#### 发送广播

### ContentProvider

#### 系统 ContentProvider

#### 自定义 ContentProvider

---

## 布局及其常用属性

### 常用的几种布局

#### 线性布局

#### 帧布局

#### 相对布局

#### 约束布局

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

#### 数据库创建于更新

#### 增删改查

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


