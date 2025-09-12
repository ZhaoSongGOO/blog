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

> Step 1 - 5 
> <img src="android/framework/app_framework/activity_launch/resources/1.png" style="width:50%">

### Step1: Launcher.startActivitysafety
> launcher 的源码用的是 android-2.3.2_r1 版本，[repo](https://android.googlesource.com/platform/packages/apps/Launcher2)

在我们点击一个 shortcut 的时候，会触发对应的点击事件监听，从响应事件的视图中获取对应的信息，并调用 `startActivitySafely`。

```java
    /**
     * Launches the intent referred by the clicked shortcut.
     *
     * @param v The view representing the clicked shortcut.
     */
    public void onClick(View v) {
        Object tag = v.getTag();
        if (tag instanceof ShortcutInfo) {
            // Open shortcut
            final Intent intent = ((ShortcutInfo) tag).intent;
            int[] pos = new int[2];
            v.getLocationOnScreen(pos);
            intent.setSourceBounds(new Rect(pos[0], pos[1],
                    pos[0] + v.getWidth(), pos[1] + v.getHeight()));
            startActivitySafely(intent, tag);
        } else {
            //...
        }
    }
```

这个 intent 中包含了对应应用的一些关键信息，如下。那 Launcher 是如何获取到这些信息的呢？系统在启动时，会启动一个 Package 管理服务 PackageManagerService，并且通过它来安装系统中的应用程序。 

PackageManagerService 在安装一个应用程序的过程中，会对它的配置文件 AndroidManifest.xml 进行解析，从而得到它里面的组件信息。系统在启动完成之后，就会将 Launcher 组件启动起来。Laucher 组件在启动过程中，会向 PackageManagerService 查询所有 Action 名称等于 “Intent.ACTION_MAIN”​，并且 Category 名称等于 “Intent.CATEGORY_LAUNCHER” 的 Activity 组件，最后为每一个 Activity 组件创建一个快捷图标，并且将它们的信息与各自的快捷图标关联起来，以便用户点击它们时可以将对应的 Activity 组件启动起来。

```txt
action="android.intent.action.MAIN"
category="android.intent.category.LAUNCHER"
cmp="com.yourapp.MainActivity" // 这个 Activity 组件的实现类。
```

`startActivitySafely` 的实现如下，给 `intent` 增加了一个 `flag` 后直接调用 `Activity` 的 `startActivity` 方法。

```java
    void startActivitySafely(Intent intent, Object tag) {
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK); // 在一个新的任务栈中启动
        try { 
            startActivity(intent);
        } //...
    }
```

### Step2: Activity.startActivity

`startActivity` 直接转调 `startActivityForResult` 并使用 -1 来标明自己并不关心结果。

```java
public void startActivity(Intent intent) {
    startActivityForResult(intent, -1);
}
```

### Step3: Activiy.startActivityForResult

- mInstrumentation 的类型为 Intrumentation，它用来监控应用程序和系统之间的交互操作。由于启动 Activity 组件是应用程序与系统之间的一个交互操作，因此调用它的成员函数 execStartActivity 来代为执行启动 Activity 组件的操作，以便它可以监控这个交互过程。
- mMainThread 的类型为 ActivityThread，用来描述一个应用程序进程。系统每当启动一个应用程序进程时，都会在它里面加载一个 ActivityThread 类实例，并且会将这个 ActivityThread 类实例保存在每一个在该进程中启动的 Activity 组件的父类 Activity 的成员变量 mMainThread 中。ActivityThread 类的成员函数 getApplicationThread 用来获取它内部的一个类型为 ApplicationThread 的 Binder 本地对象。这里将将 Launcher 组件所运行在的应用程序进程的 ApplicationThread 对象作为参数传递给成员变量 mInstrumentation 的成员函数 execStartActivity，以便可以将它传递给 ActivityManagerService，这样 ActivityManagerService 接下来就可以通过它来通知 Launcher 组件进入 Paused 状态了。
- mToken 的类型为 IBinder，它是一个 Binder 代理对象，指向了 ActivityManagerService 中一个类型为 ActivityRecord 的 Binder 本地对象。每一个已经启动的 Activity 组件在 ActivityManagerService 中都有一个对应的 ActivityRecord 对象，用来维护对应的 Activity 组件的运行状态以及信息。将 Launcher 组件的成员变量 mToken 作为参数传递给成员变量 mInstrumentation 的成员函数 execStartActivity，以便可以将它传递给 ActivityManagerService，这样 ActivityManagerService 接下来就可以获得 Launcher 组件的详细信息了。

```java
public void startActivityForResult(Intent intent, int requestCode) {
    if (mParent == null) {
        Instrumentation.ActivityResult ar =
            mInstrumentation.execStartActivity(
                this, mMainThread.getApplicationThread(), mToken, this,
                intent, requestCode);
        //...
    } else {
       //...
    }
}
```

### Step4: Instrumentation.execStartActivity

这里 getDefault() 获取的是 AMS 的远程服务代理，即 `ActivityManagerProxy`，随后调用它的 `startActivity` 方法。

```java
    public ActivityResult execStartActivity(
        Context who, IBinder contextThread, IBinder token, Activity target,
        Intent intent, int requestCode) {
        IApplicationThread whoThread = (IApplicationThread) contextThread;
        //...
        try {
            int result = ActivityManagerNative.getDefault()
                .startActivity(whoThread, intent,
                        intent.resolveTypeIfNeeded(who.getContentResolver()),
                        null, 0, token, target != null ? target.mEmbeddedID : null,
                        requestCode, false, false);
            checkStartActivityResult(result, intent);
        } catch (RemoteException e) {
        }
        return null;
    }
```

### Step5: ActivityManagerProxy.startActivity

这一步就直接通过 BinderProxy 发送一个远程请求，请求码是 `START_ACTIVITY_TRANSACTION`，借助于 binder 这个服务会被 AMS 获取。

```java
public int startActivity(IApplicationThread caller, Intent intent,
        String resolvedType, Uri[] grantedUriPermissions, int grantedMode,
        IBinder resultTo, String resultWho,
        int requestCode, boolean onlyIfNeeded,
        boolean debug) throws RemoteException {
    Parcel data = Parcel.obtain();
    Parcel reply = Parcel.obtain();
    data.writeInterfaceToken(IActivityManager.descriptor);
    data.writeStrongBinder(caller != null ? caller.asBinder() : null); // caller 应用进程的 ApplicationThread 对象
    intent.writeToParcel(data, 0); // intent 是需要启动的组件的信息
    data.writeString(resolvedType);
    data.writeTypedArray(grantedUriPermissions, 0);
    data.writeInt(grantedMode);
    data.writeStrongBinder(resultTo); // 指向一个 AMS 中的 ActivityRecord 对象，保存着 Launcher 组件信息
    data.writeString(resultWho);
    data.writeInt(requestCode);
    data.writeInt(onlyIfNeeded ? 1 : 0);
    data.writeInt(debug ? 1 : 0);
    mRemote.transact(START_ACTIVITY_TRANSACTION, data, reply, 0);
    reply.readException();
    int result = reply.readInt();
    reply.recycle();
    data.recycle();
    return result;
}
```

> Step 6 - 12
> <img src="android/framework/app_framework/activity_launch/resources/2.png" style="width:50%">

### Step6: ActivityManagerService.startActivity

mMainStack 是一个 ActivityStack 对象，用来描述一组 activity 组成的栈。

```java
public final int startActivity(IApplicationThread caller,
        Intent intent, String resolvedType, Uri[] grantedUriPermissions,
        int grantedMode, IBinder resultTo,
        String resultWho, int requestCode, boolean onlyIfNeeded,
        boolean debug) {
    return mMainStack.startActivityMayWait(caller, intent, resolvedType,
            grantedUriPermissions, grantedMode, resultTo, resultWho,
            requestCode, onlyIfNeeded, debug, null, null);
}
```

### Step7: mMainStack.startActivityMayWait

