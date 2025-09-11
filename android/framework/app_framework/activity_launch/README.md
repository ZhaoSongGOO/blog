# Activity 组件的启动过程

Activity 是 Android 应用程序的视图组件之一，负责管理 Android 应用程序的用户界面。一个应用程序一般会包含若干个 Activity 组件，每一个 Activity 组件负责一个用户界面的展现，它们可以运行在同一个进程，也可运行在不同的进程中。

从应用程序的角度出发，我们可以将Activity组件划分为两种类型：一种是根 Activity，另一种是子 Activity。根 Activity 以快捷图标的形式显示在应用程序启动器中，它的启动过程就代表了一个 Android 应用程序的启动过程。子 Activity 由根 Activity 或者其他子 Activity 启动，它们有可能与启动它们的 Activity 运行在同一个进程中，也有可能运行在不同的进程中，这取决于它们的配置和启动参数。

Activity 的启动方式分为显示和隐式两种，显示启动的 Activity 我们需要知道 Activity 对应类的名字，而对于隐式启动来说，我们只需要知道组件名称即可。

## 根 Activity 启动过程

```xml
<application
    ... >
    <activity android:name=".MainActivity"
        // process 属性代表运行当前 Activity 的进程名称
        android:process="aosp.activity.mainprocess">
        <intent-filter>
            <action android:name="android.intent.action.MAIN" />
            <category android:name="android.intent.category.LAUNCHER" />
        </intent-filter>
    </activity>
</application>
```

下面展示了一个应用的启动 Activity，就是一个根 Activity，其代表一个应用程序，在我们点击桌面图标的时候就会在一个新的应用进程中初始化，整个初始化流程包括三个进程: launcher、AMS、应用进程。

1. `Launcher` 组件向 `AMS` 发送一个启动 `MainActivity` 组件的进程间通信请求。
2. `AMS` 首先将要启动的 `MainActivity` 组件的信息保存下来，然后再向 `Launcher` 组件发送一个进入中止状态的进程间通信请求。
3. `Launcher` 组件进入到中止状态之后，就会向 `AMS` 发送一个已进入中止状态的进程间通信请求，以便 `AMS` 可以继续执行启动 `MainActivity` 组件的操作。
4. `AMS` 发现用来运行 `MainActivity` 组件的应用程序进程不存在，因此，它就会先启动一个新的应用程序进程。
5. 新的应用程序进程启动完成之后，就会向 `AMS` 发送一个启动完成的进程间通信请求，以便 `AMS` 可以继续执行启动 `MainActivity` 组件的操作。
6. `AMS` 将第 2 步保存下来的 MainActivity 组件的信息发送给第4步创建的应用程序进程，以便它可以将 MainActivity 组件启动起来。

okay! 上面六步细分的话共有 35 个小步骤，下面我们就这些步骤进行一一分析。

### 