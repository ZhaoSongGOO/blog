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

```java
final int startActivityMayWait(IApplicationThread caller,
        Intent intent, String resolvedType, Uri[] grantedUriPermissions,
        int grantedMode, IBinder resultTo,
        String resultWho, int requestCode, boolean onlyIfNeeded,
        boolean debug, WaitResult outResult, Configuration config) {
        //...
        // Don't modify the client's object!
        intent = new Intent(intent);

        // Collect information about the target of the Intent. 使用 PMS 搜集应用程序的信息
        ActivityInfo aInfo;
        try {
            ResolveInfo rInfo =
                AppGlobals.getPackageManager().resolveIntent(
                        intent, resolvedType,
                        PackageManager.MATCH_DEFAULT_ONLY
                        | ActivityManagerService.STOCK_PM_FLAGS);
            aInfo = rInfo != null ? rInfo.activityInfo : null;
        } catch (RemoteException e) {
            aInfo = null;
        }
        synchronized (mService) {
        //...
        // 调用成员函数startActivityLocked来继续执行启动Activity组件的工作
        int res = startActivityLocked(caller, intent, resolvedType,
                grantedUriPermissions, grantedMode, aInfo,
                resultTo, resultWho, requestCode, callingPid, callingUid,
                onlyIfNeeded, componentSpecified);
        //...
        return res;
        }
}
```

### Step8: int ActivityStack.startActivityLocked

在 AMS 中，每一个应用进程都使用一个 ProcessRecord 对象来描述，并且保存在 AMS 内部 (mLruProcesses)。

ActivityStack 的 mService 就是 AMS，这里先试用 AMS 的 getRecordForAppLocked 来获取 launcher 程序的 ProcessRecord。

随后从 mHistory (ArrayList) 中拿到对应的 ActivityRecord 组件。

通过这些信息对即将启动的 Activity 创建一个 ActivityRecord 组件，并进一步调用 startActivityUncheckedLocked。

```java
final int startActivityLocked(IApplicationThread caller,
            Intent intent, String resolvedType,
            Uri[] grantedUriPermissions,
            int grantedMode, ActivityInfo aInfo, IBinder resultTo,
            String resultWho, int requestCode,
            int callingPid, int callingUid, boolean onlyIfNeeded,
            boolean componentSpecified) {

        int err = START_SUCCESS;

        ProcessRecord callerApp = null;
        if (caller != null) {
            callerApp = mService.getRecordForAppLocked(caller);
            if (callerApp != null) {
                callingPid = callerApp.pid;
                callingUid = callerApp.info.uid;
            } else {
                Slog.w(TAG, "Unable to find app for caller " + caller
                      + " (pid=" + callingPid + ") when starting: "
                      + intent.toString());
                err = START_PERMISSION_DENIED;
            }
        }

        if (err == START_SUCCESS) {
            Slog.i(TAG, "Starting: " + intent + " from pid "
                    + (callerApp != null ? callerApp.pid : callingPid));
        }

        ActivityRecord sourceRecord = null;
        ActivityRecord resultRecord = null;
        if (resultTo != null) {
            int index = indexOfTokenLocked(resultTo);
            if (DEBUG_RESULTS) Slog.v(
                TAG, "Sending result to " + resultTo + " (index " + index + ")");
            if (index >= 0) {
                sourceRecord = (ActivityRecord)mHistory.get(index);
                // 因为源 activity 不关心返回结果 (requestCode <0)，所以 resultRecord 为 null。
                if (requestCode >= 0 && !sourceRecord.finishing) {
                    resultRecord = sourceRecord;
                }
            }
        }

        //...
        // 创建一个 ActivityRecord 组件描述即将创建的 Activity。
        ActivityRecord r = new ActivityRecord(mService, this, callerApp, callingUid,
                intent, resolvedType, aInfo, mService.mConfiguration,
                resultRecord, resultWho, requestCode, componentSpecified);

        //...
        
        return startActivityUncheckedLocked(r, sourceRecord,
                grantedUriPermissions, grantedMode, onlyIfNeeded, true);
    }
```

### Step9:ActivityStack.startActivityUncheckedLocked

1. 首先通过 intent.getFlags 拿到 activity 的启动标志位，从前面的Step 1可以知道，在变量 launchFlags 中，只有 Intent.FLAG_ACTIVITY_NEW_TASK 位被设置为1，其他位均等于0。
2. 检查变量 launchFlags 的 Intent.FLAG_ACTIVITY_NO_USER_ACTION 位是否等于 1。如果等于 1，那么就表示目标 Activity 组件不是由用户手动启动的。如果目标 Activity 组件是由用户手动启动的，那么用来启动它的源 Activity 组件就会获得一个用户离开事件通知。由于目标 Activity 组件是用户在应用程序启动器的界面上点击启动的，即变量 launchFlags 的 Intent.FLAG_ACTIVITY_NO_USER_ACTION 位等于 0；因此，成员变量 mUserLeaving 的值就等于 true，表示后面要向源 Activity 组件发送一个用户离开事件通知。
3. addingToTask, 标志这个 Activity 所处的任务是不是已经创建。
4. 随后创建一个新的 TaskRecord, 并交给 AMS 来管理。
5. 随后调用另外一个 startActivityLocked 来进行后续操作。

> [在 AMS 中，TaskRecord ，ProcessRecord 和 ActivityRecord 的关系是什么?](android/framework/app_framework/ref/ar_pr_tr.md)

```java
 final int startActivityUncheckedLocked(ActivityRecord r,
            ActivityRecord sourceRecord, Uri[] grantedUriPermissions,
            int grantedMode, boolean onlyIfNeeded, boolean doResume) {
        final Intent intent = r.intent;
        final int callingUid = r.launchedFromUid;

        // 1. 检查启动标志位
        int launchFlags = intent.getFlags();
        
        // We'll invoke onUserLeaving before onPause only if the launching
        // activity did not explicitly state that this is an automated launch.
        // 2. 判断是不是用户操作导致的离开源 activity。
        mUserLeaving = (launchFlags&Intent.FLAG_ACTIVITY_NO_USER_ACTION) == 0;
        
        //...

        //3. 先设置成 false，后续还会 AMS 会检测是不是创建了，但是在我们的场景下，没有创建，这个值一直都是 false。
        boolean addingToTask = false;

        //...

        boolean newTask = false;

        // Should this be considered a new task?
        if (r.resultTo == null && !addingToTask
                && (launchFlags&Intent.FLAG_ACTIVITY_NEW_TASK) != 0) {
            // todo: should do better management of integers.
            mService.mCurTask++;
            if (mService.mCurTask <= 0) {
                mService.mCurTask = 1;
            }
            // 创建一个新任务栈
            r.task = new TaskRecord(mService.mCurTask, r.info, intent,
                    (r.info.flags&ActivityInfo.FLAG_CLEAR_TASK_ON_LAUNCH) != 0);
            if (DEBUG_TASKS) Slog.v(TAG, "Starting new activity " + r
                    + " in new task " + r.task);
            newTask = true;
            if (mMainStack) {
                // 由 AMS 来管理 Task
                mService.addRecentTaskLocked(r.task);
            }
            
        } else if (sourceRecord != null) {
            //...
        } 
        //...
        startActivityLocked(r, newTask, doResume);
        return START_SUCCESS;
    }
```

在这个 startActivityLocked 函数中执行了下面的两件事：

1. 当目标 Activity 组件是在一个新创建的任务中启动时，即参数 newTask 的值等于true时，ActivityStack 就需要将它放在 Activity 组件堆栈的最上面，即将变量 addPos 的值设置为 Activity 组件堆栈的当前大小 NH，以便接下来可以将它激活。
2. 调用成员函数 resumeTopActivityLocked 将 Activity 组件堆栈顶端的 Activity 组件激活，这个 Activity 组件就正好是即将要启动的 MainActivity 组件。

```java
    private final void startActivityLocked(ActivityRecord r, boolean newTask,
            boolean doResume) {
        final int NH = mHistory.size();

        int addPos = -1;
        
        //...
        if(!newTask){
            //...
        }

        // Place a new activity at top of stack, so it is next to interact
        // with the user.
        if (addPos < 0) {
            addPos = NH;
        }
        
        //...
        
        // Slot the activity into the history stack and proceed
        mHistory.add(addPos, r);
        //...

        if (doResume) {
            resumeTopActivityLocked(null);
        }
    }
```

### Step10. ActivityStack.resumeTopActivityLocked

1. 调用成员函数 topRunningActivityLocked 来获得当前 Activity 组件堆栈最上面的一个不是处于结束状态的 Activity 组件, 即 MainActivity.
2. ActivityStack 类有三个成员变量 mResumedActivity、mLastPausedActivity 和 mPausingActivity，它们的类型均为 ActivityRecord，分别用来描述系统当前激活的 Activity 组件、上一次被中止的 Activity 组件，以及正在被中止的 Activity 组件。这个场景下，mResumedActivity 就是 Launcher 组件的 Activity。


```java
 final boolean resumeTopActivityLocked(ActivityRecord prev) {
        // Find the first activity that is not finishing.
        ActivityRecord next = topRunningActivityLocked(null);

        // Remember how we'll process this pause/resume situation, and ensure
        // that the state is reset however we wind up proceeding.
        final boolean userLeaving = mUserLeaving;
        mUserLeaving = false;

        //...
        
        // If the top activity is the resumed one, nothing to do.
        // 检查即将要启动的 Activity 组件 next 是否等于当前被激活的 Activity 组件。如果等于，并且它的状态为 Resumed，那么就可以直接返回了，因为要启动的 Activity 组件本身就已经启动和激活了。
        if (mResumedActivity == next && next.state == ActivityState.RESUMED) {
            // Make sure we have executed any pending transitions, since there
            // should be nothing left to do at this point.
            mService.mWindowManager.executeAppTransition();
            mNoAnimActivities.clear();
            return false;
        }

        // If we are sleeping, and there is no resumed activity, and the top
        // activity is paused, well that is the state we want.
        // 检查即将要启动的 Activity 组件 next 是否等于上一次被中止了的 Activity 组件。如果等于，并且这时候系统正要进入关机或者睡眠状态，那么也可以直接返回了，因为这时候将这个 Activity 组件启动起来是没有意义的。
        if ((mService.mSleeping || mService.mShuttingDown)
                && mLastPausedActivity == next && next.state == ActivityState.PAUSED) {
            // Make sure we have executed any pending transitions, since there
            // should be nothing left to do at this point.
            mService.mWindowManager.executeAppTransition();
            mNoAnimActivities.clear();
            return false;
        }
        
        //...

        // If we are currently pausing an activity, then don't do anything
        // until that is done.
        // 检查系统当前是否正在中止一个 Activity 组件。如果是，那么就要等到它中止完成之后，再启动 Activity 组件 next，因此，也直接返回了。
        if (mPausingActivity != null) {
            if (DEBUG_SWITCH) Slog.v(TAG, "Skip resume: pausing=" + mPausingActivity);
            return false;
        }

        //...
        
        // We need to start pausing the current activity so the top one
        // can be resumed...
        // 调用成员函数 startPausingLocked 来通知 Launcher 组件进入 Paused 状态，以便它可以将焦点让给即将要启动的 MainActivity 组件。
        if (mResumedActivity != null) {
            if (DEBUG_SWITCH) Slog.v(TAG, "Skip resume: need to start pausing");
            startPausingLocked(userLeaving, false);
            return true;
        }

        //...
    }
```

### Step11: ActivityStack.startPausingLocked

1. 将 prev、成员变量 mPausingActivity 和 mLastPausedActivity 指向 launcher 组件。为啥呢，因为 MainActivity 激活后，Launcher 组件就是那个需要被 pausing 的。
2. ActivityRecord 成员 app 是一个 ProcessRecord，用来描述 Activity 组件所运行在的应用程序进程。而 ProcessRecord 类又有一个成员变量 thread，它的类型为 ApplicationThreadProxy，用来描述一个 Binder 代理对象，引用的是一个类型为 ApplicationThread 的 Binder 本地对象。这里使用 prev.app.thread.schedulePauseActivity 向 launcher 组件发送一个消息，让其终止自己的运行。
3. Launcher 组件处理完 ActivityManagerService 给它发送的中止通知之后，必须再向 ActivityManagerService 发送一个启动 MainActivity 组件的通知，以便 ActivityManagerService 可以将位于 Activity  组件堆栈顶端的MainActivity 组件启动起来。但是，ActivityManagerService 不能无限地等待，因此，就向 ActivityManagerService 所运行在的线程的消息队列发送一个类型为 PAUSE_TIMEOUT_MSG 的消息，并且指定这个消息在 PAUSE_TIMEOUT 毫秒之后处理。如果 Launcher 组件不能在 PAUSE_TIMEOUT 毫秒内再向 ActivityManagerService 发送一个启动 MainActivity 组件的通知，那么 ActivityManagerService 就会认为它没有响应了。

```java
    private final void startPausingLocked(boolean userLeaving, boolean uiSleeping) {
        //...
        ActivityRecord prev = mResumedActivity;
        if (prev == null) {
            RuntimeException e = new RuntimeException();
            Slog.e(TAG, "Trying to pause when nothing is resumed", e);
            resumeTopActivityLocked(null);
            return;
        }
        if (DEBUG_PAUSE) Slog.v(TAG, "Start pausing: " + prev);
        mResumedActivity = null;
        mPausingActivity = prev;
        mLastPausedActivity = prev;
        prev.state = ActivityState.PAUSING;

        //...
        
        if (prev.app != null && prev.app.thread != null) {
            try {
                //...
                // 2. 远程调用，让 launcher 进入 pausing 状态
                prev.app.thread.schedulePauseActivity(prev, prev.finishing, userLeaving,
                        prev.configChangeFlags);
                if (mMainStack) {
                    mService.updateUsageStats(prev, false);
                }
            } catch (Exception e) {
               //...
            }
        } else {
            mPausingActivity = null;
            mLastPausedActivity = null;
        }

        //...


        if (mPausingActivity != null) {
            //...

            // Schedule a pause timeout in case the app doesn't respond.
            // We don't give it much time because this directly impacts the
            // responsiveness seen by the user.
            // 3. 发送消息等待 launcher 组件 pausing 成功。
            Message msg = mHandler.obtainMessage(PAUSE_TIMEOUT_MSG);
            msg.obj = prev;
            mHandler.sendMessageDelayed(msg, PAUSE_TIMEOUT);
            if (DEBUG_PAUSE) Slog.v(TAG, "Waiting for pause to complete...");
        } else {
            // This activity failed to schedule the
            // pause, so just treat it as being paused now.
            if (DEBUG_PAUSE) Slog.v(TAG, "Activity not running, resuming next.");
            resumeTopActivityLocked(null);
        }
    }
```

### Step12: ApplicationThreadProxy.schedulePauseActivity

这个 Proxy 本身就是发送一个远程通信，把 token (launcher 对应的 ActivityRecord 代理) 发送到 ActivityThread.

```java
public final void schedulePauseActivity(IBinder token, boolean finished,
        boolean userLeaving, int configChanges) throws RemoteException {
    Parcel data = Parcel.obtain();
    data.writeInterfaceToken(IApplicationThread.descriptor);
    data.writeStrongBinder(token);
    data.writeInt(finished ? 1 : 0);
    data.writeInt(userLeaving ? 1 :0);
    data.writeInt(configChanges);
    mRemote.transact(SCHEDULE_PAUSE_ACTIVITY_TRANSACTION, data, null,
            IBinder.FLAG_ONEWAY);
    data.recycle();
}
```

> Step 13 - 17 
> <img src="android/framework/app_framework/activity_launch/resources/3.png" style="width:50%">

### Step13 ApplicationThread.schedulePauseActivity

这个方法调用外部类 ActivityThread 的 queueOrSendMessage 来发送消息。

```java
public final void schedulePauseActivity(IBinder token, boolean finished,
        boolean userLeaving, int configChanges) {
    queueOrSendMessage(
            finished ? H.PAUSE_ACTIVITY_FINISHING : H.PAUSE_ACTIVITY,
            token,
            (userLeaving ? 1 : 0),
            configChanges);
}
```

### Step14 ActivityThread.queueOrSendMessage

> [Handler 和 Looper](android/framework/app_framework/ref/handler_looper.md)

成员变量 mH 是一个继承了 Handler 的对象，用来发送和处理主线程的消息。

```java
private final void queueOrSendMessage(int what, Object obj, int arg1, int arg2) {
    synchronized (this) {
        if (DEBUG_MESSAGES) Slog.v(
            TAG, "SCHEDULE " + what + " " + mH.codeToString(what)
            + ": " + arg1 + " / " + obj);
        Message msg = Message.obtain();
        msg.what = what;
        msg.obj = obj;
        msg.arg1 = arg1;
        msg.arg2 = arg2;
        mH.sendMessage(msg);
    }
}
```

### Step15 H.handleMessage

上面的 mH 发送消息后，最终消息会调用 handleMessage 来处理。

```java
public void handleMessage(Message msg) {
    if (DEBUG_MESSAGES) Slog.v(TAG, ">>> handling: " + msg.what);
    switch (msg.what) {
        //...
        case PAUSE_ACTIVITY:
            handlePauseActivity((IBinder)msg.obj, false, msg.arg1 != 0, msg.arg2);
            maybeSnapshot();
            break;
        //...
    }
    //...
}
```

### Step16 ActivityThread.handlePauseActivity

在应用程序进程中启动的每一个 Activity 组件都使用一个 ActivityClientRecord 对象来描述，这些 ActivityClientRecord 对象对应于 ActivityManagerService 中的 ActivityRecord  对象，并且保存在ActivityThread 类的成员变量 mActivities 中。

获得了要中止的目标 Activity 组件之后，ActivityThread 类的成员函数 handlePauseActivity 接下来做了三件事情。

第一件事情是调用成员函数 performUserLeavingActivity 向 Launcher 组件发送一个用户离开事件通知，即调用它的成员函数 onUserLeaveHint。

第二件事情是调用成员函数 performPauseActivity 向 Launcher 组件发送一个中止事件通知，即调用它的成员函数 onPause。

第三件事情是调用 QueuedWork 类的静态成员函数 waitToFinish 等待完成前面的一些数据写入操作，例如，将数据写入到磁盘的操作。由于现在 Launcher 组件即将要进入 Paused 状态了，因此就要保证它前面的所有数据写入操作都处理完成；否则，等到它重新进入 Resumed 状态时，就无法恢复之前所保存的一些状态数据。

最后通过远程调用到 AMS 的 activityPaused 方法。

```java
final HashMap<IBinder, ActivityClientRecord> mActivities
        = new HashMap<IBinder, ActivityClientRecord>();
//...
private final void handlePauseActivity(IBinder token, boolean finished,
        boolean userLeaving, int configChanges) {
    ActivityClientRecord r = mActivities.get(token);
    if (r != null) {
        //Slog.v(TAG, "userLeaving=" + userLeaving + " handling pause of " + r);
        if (userLeaving) {
            performUserLeavingActivity(r);
        }

        r.activity.mConfigChangeFlags |= configChanges;
        Bundle state = performPauseActivity(token, finished, true);

        // Make sure any pending writes are now committed.
        QueuedWork.waitToFinish();
        
        // Tell the activity manager we have paused.
        try {
            ActivityManagerNative.getDefault().activityPaused(token, state);
        } catch (RemoteException ex) {
        }
    }
}
```

### Step17 ActivityManagerProxy.activityPaused

传入的参数是 Activity 在 AMS 中的 ActivityRecord 远程对象以及 Pause 的执行结果。

```java
public void activityPaused(IBinder token, Bundle state) throws RemoteException
{
    Parcel data = Parcel.obtain();
    Parcel reply = Parcel.obtain();
    data.writeInterfaceToken(IActivityManager.descriptor);
    data.writeStrongBinder(token);
    data.writeBundle(state);
    mRemote.transact(ACTIVITY_PAUSED_TRANSACTION, data, reply, 0);
    reply.readException();
    data.recycle();
    reply.recycle();
}
```

---
> Step 18 - 23 
> <img src="android/framework/app_framework/activity_launch/resources/4.png" style="width:50%">
---

### Step18 ActivityManagerService.activityPaused

```java
    public final void activityPaused(IBinder token, Bundle icicle) {
        //...
        mMainStack.activityPaused(token, icicle, false);
        //...
    }
```

### Step19 ActivityStack.activityPaused

第一，先找到 launcher token 对应的 ActivityRecord 对象。
第二，因为已经收到了 Pause 消息，所以移除超时操作。
第三，设置 launcher activity 的状态为 PAUSE。
第四，启动 MainActivity.


```java
final void activityPaused(IBinder token, Bundle icicle, boolean timeout) {
    if (DEBUG_PAUSE) Slog.v(
        TAG, "Activity paused: token=" + token + ", icicle=" + icicle
        + ", timeout=" + timeout);

    ActivityRecord r = null;

    synchronized (mService) {
        //1. 找到 launcher 对应的 activity
        int index = indexOfTokenLocked(token);
        if (index >= 0) {
            r = (ActivityRecord)mHistory.get(index);
            if (!timeout) {
                r.icicle = icicle;
                r.haveState = true;
            }
            //2. 移除超时操作
            mHandler.removeMessages(PAUSE_TIMEOUT_MSG, r);
            if (mPausingActivity == r) {
                //3. 设置 Activity 的状态
                r.state = ActivityState.PAUSED;
                //4. 启动 MainActivity.
                completePauseLocked();
            } else {
                EventLog.writeEvent(EventLogTags.AM_FAILED_TO_PAUSE,
                        System.identityHashCode(r), r.shortComponentName, 
                        mPausingActivity != null
                            ? mPausingActivity.shortComponentName : "(none)");
            }
        }
    }
}
```

### Step20 ActivityStack.completePauseLocked

第一步，将当前 mPausingActivity 设置为 null，因为 launcher activity 已经进入了 Pausing 状态。
第二步，resumeTopActivityLocked 启动堆栈顶部的 activity。

```java
    private final void completePauseLocked() {
        ActivityRecord prev = mPausingActivity;
        if (DEBUG_PAUSE) Slog.v(TAG, "Complete pause: " + prev);
        
        if (prev != null) {
            //...
            //1. 当前 activity 已经进入了 pausing 状态，所以设置为 null。
            mPausingActivity = null;
        }

        if (!mService.mSleeping && !mService.mShuttingDown) {
            //2. 启动堆栈顶部的 activity
            resumeTopActivityLocked(prev);
        } 
        //...
    }
```

### Step21 ActivityStack.resumeTopActivityLocked

在前面的 Step10 中，ActivityManagerService 已经调用过它的成员函数 resumeTopActivityLocked 来试图启动 MainActivity 组件了；但是由于那时候 Launcher 组件尚未进入 Paused 状态，即 ActivityStack 类的成员变量 mResumedActivity 不等于 null，因此，就会先调用成员函数 startPausingLocked 来执行中止 Launcher 组件的操作。

在前面的 Step11 中，ActivityManagerService 在向 Launcher 组件发送中止通知之前，已经将 ActivityStack 类的成员变量 mResumedActivity 设置为 null 了，因此，这时候就会 成员函数topRunningActivityLocked。

对象 next 获得的是位于 Activity 组件堆栈顶端的，与即将启动的 MainActivity 组件对应的一个 ActivityRecord。由于这时候 MainActivity 组件尚未被启动起来，因此，它的成员变量 app 就会等于 null，接下来就会调用成员函数 startSpecificActivityLocked 将它启动起来。

```java
    final boolean resumeTopActivityLocked(ActivityRecord prev) {
        // Find the first activity that is not finishing.
        ActivityRecord next = topRunningActivityLocked(null);
        //...
        
        // We need to start pausing the current activity so the top one
        // can be resumed...
        if (mResumedActivity != null) {
            if (DEBUG_SWITCH) Slog.v(TAG, "Skip resume: need to start pausing");
            startPausingLocked(userLeaving, false);
            return true;
        }

        //...

        if (next.app != null && next.app.thread != null) {
            //...
        } else {
            //...
            startSpecificActivityLocked(next, true, true);
        }

        return true;
    }
```

### Step22 ActivityStack.startSpecificActivityLocked

在 ActivityManagerService 中，每一个 Activity 组件都有一个用户 ID 和一个进程名称；其中，用户 ID 是在安装该 Activity 组件时由 PackageManagerService 分配的，而进程名称则是由该 Activity 组件的 `android:process` 属性来决定的。ActivityManagerService 在启动一个 Activity 组件时，首先会以它的用户 ID 和进程名称来检查系统中是否存在一个对应的应用程序进程。如果存在，就会直接通知这个应用程序进程将该 Activity 组件启动起来；否则，就会先以这个用户 ID 和进程名称来创建一个应用程序进程，然后再通知这个应用程序进程将该 Activity 组件启动起来。

第一步检查与 ActivityRecord 对象 r 对应的 Activity 组件所需要的应用程序进程是否已经存在。如果存在，就直接调用成员函数 realStartActivityLocked 来启动该 Activity 组件；否则，就会先调用 ActivityManagerService类的成员函数 startProcessLocked 为该 Activity 组件创建一个应用程序进程，然后再将它启动起来。

由于 MainActivity 组件是第一次被启动，即这时候系统中是不可能存在所需要的应用程序进程的，因此，接下来就会调用 ActivityManagerService 类的成员函数 startProcessLocked 来为 MainActivity 组件创建一个应用程序进程。

```java
private final void startSpecificActivityLocked(ActivityRecord r,
        boolean andResume, boolean checkConfig) {
    // Is this activity's application already running?
    ProcessRecord app = mService.getProcessRecordLocked(r.processName,
            r.info.applicationInfo.uid);
    //...
    
    // app == null
    if (app != null && app.thread != null) {
        try {
            realStartActivityLocked(r, app, andResume, checkConfig);
            return;
        } catch (RemoteException e) {
            Slog.w(TAG, "Exception when starting activity "
                    + r.intent.getComponent().flattenToShortString(), e);
        }

        // If a dead object exception was thrown -- fall through to
        // restart the application.
    }

    mService.startProcessLocked(r.processName, r.info.applicationInfo, true, 0,
            "activity", r.intent.getComponent(), false);
}
```

### Step23 ActivityServiceManager.startProcessLocked

首先检查请求创建的应用程序进程是否已经存在了。如果不存在，就会根据指定的名称以及用户 ID 来创建一个 ProcessRecord 对象，并且将它保存在 ActivityManagerService 类的成员变量 mProcessNames 中。

```java
    final ProcessRecord startProcessLocked(String processName,
            ApplicationInfo info, boolean knownToBeDead, int intentFlags,
            String hostingType, ComponentName hostingName, boolean allowWhileBooting) {
        ProcessRecord app = getProcessRecordLocked(processName, info.uid);
        //...

        String hostingNameStr = hostingName != null
                ? hostingName.flattenToShortString() : null;
        //...
        
        if (app == null) {
            app = newProcessRecordLocked(null, info, processName);
            mProcessNames.put(processName, info.uid, app);
        } 
        //...

        startProcessLocked(app, hostingType, hostingNameStr);
        return (app.pid != 0) ? app : null;
    }
```

随后调用一个重载版本的 startProcessLocked 方法。

使用 `Process.start` 方法来创建一个进程，这个操作会返回进程的id `pid`。然后以变量 pid 为关键字将参数 app 所指向的一个 ProcessRecord 对象保存在 ActivityManagerService 类的成员变量 mPidsSelfLocked 中。

最后代码向 ActivityManagerService 所运行在的线程的消息队列中发送一个类型为 PROC_START_TIMEOUT_MSG 的消息，并且指定这个消息在 PROC_START_TIMEOUT 毫秒之后处理。新的应用程序进程必须在 PROC_START_TIMEOUT 毫秒之内完成启动工作，并且向 ActivityManagerService 发送一个启动完成的通知，以便 ActivityManagerService 可以在它里面启动一个 Activity 组件；否则，ActivityManagerService 就会认为它启动超时了，因此，就不能将相应的 Activity 组件启动起来。


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
                Slog.w(TAG, "Unable to retrieve gids", e);
            }
            //...
            int debugFlags = 0;
            //...
            // 指定该进程的入口函数为 android.app.ActivityThread 类的静态成员函数 main
            int pid = Process.start("android.app.ActivityThread",
                    mSimpleProcessManagement ? app.processName : null, uid, uid,
                    gids, debugFlags, null);
            //...
            if (pid == 0 || pid == MY_PID) {
                //...
            } else if (pid > 0) {
                app.pid = pid;
                app.removed = false;
                synchronized (mPidsSelfLocked) {
                    this.mPidsSelfLocked.put(pid, app);
                    Message msg = mHandler.obtainMessage(PROC_START_TIMEOUT_MSG);
                    msg.obj = app;
                    mHandler.sendMessageDelayed(msg, PROC_START_TIMEOUT);
                }
            } else {
                //...
            }
        } catch (RuntimeException e) {
            //...
        }
    }
```

---

在创建进程的时候，我们指定那个进程初始化后，执行的 java 层代码是 android.app.ActivityThread 类的静态成员函数 main。

---

### Step24 ActivityThread.main

新的应用程序进程在启动时，主要做了两件事情。

第一，在进程中创建了一个 ActivityThread 对象，并且调用它的成员函数 attch 向 AMS 发送一个启动完成通知。

第三，调用 Looper 类的静态成员函数 prepareMainLooper 创建一个消息循环，并且在发送完成通知后，是的当前进程进入消息循环中。

```java
public final class ActivityThread {
    final ApplicationThread mAppThread = new ApplicationThread();
    //...
    private final void attach(boolean system) {
        //...
        mSystemThread = system;
        if (!system) {
            //...
            IActivityManager mgr = ActivityManagerNative.getDefault();
            try {
                mgr.attachApplication(mAppThread);
            } catch (RemoteException ex) {
            }
        } 
        //...
    }

    private final void detach()
    {
        sThreadLocal.set(null);
    }
    //...

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
}
```

在创建 ActivityThread 对象 thread 时，会同时在它内部创建一个 ApplicationThread 对象 mAppThread。

前面提到，ActivityThread 对象内部的 ApplicationThread 对象是一个 Binder 本地对象，AMS 就是通过它来和应用程序进程通信的。在 ActivityThread 类的成员函数 attach 中，首先调用 ActivityManagerNative 类的静态成员函数 getDefault 来获得 AMS 的一个代理对象；然后它的成员函数 attachApplication 向 AMS 发送一个进程间通信请求，并且将前面所创建的 ApplicationThread 对象传递给 AMS。AMS 代理对象的类型为 ActivityManagerProxy，因此，接下来就会调用 ActivityManagerProxy 类的成员函数向 AMS 发送一个进程间通信请求。

### Step25 ActivityManagerProxy.attachApplication

向 AMS 发送一个类型为 `ATTACH_APPLICATION_TRANSACTION` 的进程间通信请求。

```java
    public void attachApplication(IApplicationThread app) throws RemoteException
    {
        Parcel data = Parcel.obtain();
        Parcel reply = Parcel.obtain();
        data.writeInterfaceToken(IActivityManager.descriptor);
        data.writeStrongBinder(app.asBinder());
        mRemote.transact(ATTACH_APPLICATION_TRANSACTION, data, reply, 0);
        reply.readException();
        data.recycle();
        reply.recycle();
    }
```

### Step26 ActivityManagerService.attachApplication

转调 `attachApplicationLocked` 执行操作。


```java
    public final void attachApplication(IApplicationThread thread) {
        synchronized (this) {
            int callingPid = Binder.getCallingPid();
            final long origId = Binder.clearCallingIdentity();
            attachApplicationLocked(thread, callingPid);
            Binder.restoreCallingIdentity(origId);
        }
    }
```

### Step27 ActivityManagerService.attachApplicationLocked

参数 pid 指向了前面所创建的应用程序进程的 PID。在前面的 Step23 中，ActivityManagerService 以这个 PID 为关键字将一个 ProcessRecord 对象保存在了成员变量 mPidsSelfLocked中。因此，就可以通过参数 pid 将这个 ProcessRecord 对象取回来，并且保存在变量 app 中。

前面得到的 ProcessRecord 对象 app 就是用来描述新创建的应用程序进程的。现在既然这个应用程序进程已经启动起来了，就继续对 ProcessRecord 对象 app 进行初始化，其中，最重要的是将它的成员变量 thread 设置为参数 thread 所指向的一个 ApplicationThread 代理对象。这样，AMS 以后就可以通过这个 ApplicationThread 代理对象来和新创建的应用程序进程进行通信了。

然后既然 Activity 启动的消息已经发过来了，那就移除超时的信息。

最后得到位于 Activity 组件堆栈顶端的一个 ActivityRecord 对象 hr，与它对应的 Activity 组件就是即将要启动的 MainActivity 组件，检查这个 Activity 组件的用户 ID 和进程名称是否与 ProcessRecord 对象 app 所描述的应用程序进程的用户 ID 和进程名称一致。如果一致，那么就说明 ActivityRecord 对象 hr 所描述的 Activity 组件是应该在 ProcessRecord 对象 app 所描述的应用程序进程中启动的，因此，就会调用 ActivityStack 类的成员函数 realStartActivityLocked 来请求该应用程序进程启动一个 Activity 组件。

```java
    private final boolean attachApplicationLocked(IApplicationThread thread,
            int pid) {

        // Find the application record that is being attached...  either via
        // the pid if we are running in multiple processes, or just pull the
        // next app record if we are emulating process with anonymous threads.
        ProcessRecord app;
        if (pid != MY_PID && pid >= 0) {
            synchronized (mPidsSelfLocked) {
                app = mPidsSelfLocked.get(pid);
            }
        } 
        //...
        String processName = app.processName;
        //...
        
        app.thread = thread;
        app.curAdj = app.setAdj = -100;
        app.curSchedGroup = Process.THREAD_GROUP_DEFAULT;
        app.setSchedGroup = Process.THREAD_GROUP_BG_NONINTERACTIVE;
        app.forcingToForeground = null;
        app.foregroundServices = false;
        app.debugging = false;

        mHandler.removeMessages(PROC_START_TIMEOUT_MSG, app);

        boolean normalMode = mProcessesReady || isAllowedWhileBooting(app.info);
        //...

        // See if the top visible activity is waiting to run in this process...
        ActivityRecord hr = mMainStack.topRunningActivityLocked(null);
        if (hr != null && normalMode) {
            if (hr.app == null && app.info.uid == hr.info.applicationInfo.uid
                    && processName.equals(hr.processName)) {
                try {
                    if (mMainStack.realStartActivityLocked(hr, app, true, true)) {
                        didSomething = true;
                    }
                } catch (Exception e) {
                    //...
                }
            } else {
                //...
            }
        }
        //...
        return true;
    }
```

### Step28 ActivityStack.realStartActivityLocked

接下来 ActivityRecord 就要在指定的 ProcessRecord 中开始运行了。随后就是使用 ApplicationThread 的远程调用触发 ApplicationThread 中的 scheduleLaunchActivity 方法。

```java
    final boolean realStartActivityLocked(ActivityRecord r,
            ProcessRecord app, boolean andResume, boolean checkConfig)
            throws RemoteException {
        //...

        r.app = app;

        int idx = app.activities.indexOf(r);
        if (idx < 0) {
            app.activities.add(r);
        }
        //...

        try {
            //...
            List<ResultInfo> results = null;
            List<Intent> newIntents = null;
            if (andResume) {
                results = r.results;
                newIntents = r.newIntents;
            }
            //...
            app.thread.scheduleLaunchActivity(new Intent(r.intent), r,
                    System.identityHashCode(r),
                    r.info, r.icicle, results, newIntents, !andResume,
                    mService.isNextTransitionForward());
            //...
        } catch (RemoteException e) {
            //...
        }
        //...        
        return true;
    }
```

### Step29 ApplicationThreadProxy.scheduleLaunchActivity

上一步中，AMS 拿到的 thread 其实是一个代理对象 ApplicationThreadProxy，代理的是之前创建的新进程中的 ApplicationThread 对象，即 mAppThread。

```java
public final void scheduleLaunchActivity(Intent intent, IBinder token, int ident,
        ActivityInfo info, Bundle state, List<ResultInfo> pendingResults,
        List<Intent> pendingNewIntents, boolean notResumed, boolean isForward)
        throws RemoteException {
    Parcel data = Parcel.obtain();
    data.writeInterfaceToken(IApplicationThread.descriptor);
    intent.writeToParcel(data, 0);
    data.writeStrongBinder(token);
    data.writeInt(ident);
    info.writeToParcel(data, 0);
    data.writeBundle(state);
    data.writeTypedList(pendingResults);
    data.writeTypedList(pendingNewIntents);
    data.writeInt(notResumed ? 1 : 0);
    data.writeInt(isForward ? 1 : 0);
    mRemote.transact(SCHEDULE_LAUNCH_ACTIVITY_TRANSACTION, data, null,
            IBinder.FLAG_ONEWAY);
    data.recycle();
}
```

### Step30 ApplicationThread.scheduleLaunchActivity

ApplicationThread 类的成员函数 scheduleLaunchActivity 用来处理类型为 SCHEDULE_LAUNCH_ACTIVITY_TRANSACTION 的进程间通信请求，它主要是将要启动的 Activity 组件的信息封装成一个 ActivityClientRecord 对象，然后再以这个 ActivityClientRecord 对象为参数来调用 ActivityThread 类的成员函数 queueOrSendMessage，以便可以往新创建的应用程序进程的主线程的消息队列发送一个类型为 LAUNCH_ACTIVITY 的消息。


```java
public final void scheduleLaunchActivity(Intent intent, IBinder token, int ident,
        ActivityInfo info, Bundle state, List<ResultInfo> pendingResults,
        List<Intent> pendingNewIntents, boolean notResumed, boolean isForward) {
    ActivityClientRecord r = new ActivityClientRecord();

    r.token = token;
    r.ident = ident;
    r.intent = intent;
    r.activityInfo = info;
    r.state = state;

    r.pendingResults = pendingResults;
    r.pendingIntents = pendingNewIntents;

    r.startsNotResumed = notResumed;
    r.isForward = isForward;

    queueOrSendMessage(H.LAUNCH_ACTIVITY, r);
}
```

### Step31 ActivityThread.queueOrSendMessage

这个和之前一样都是使用外部类 ActivityThread 的 queueOrSendMessage 方法给主线程发送了一个消息。


### Step32

首先调用成员函数 getPackageInfoNoCheck 来获得一个 LoadedApk 对象，并且保存在 ActivityClientRecord 对象 r 的成员变量 packageInfo 中。

我们知道，每一个 Android 应用程序都是打包在一个 Apk 文件中的。一个 Apk 文件包含了一个 Android 应用程序的所有资源，应用程序进程在启动一个 Activity 组件时，需要将它所属的 Apk 文件加载进来，以便可以访问它里面的资源。在 ActivityThread 类内部，就使用一个 LoadedApk 对象来描述一个已加载的 Apk 文件。

最后，调用 ActivityThread 类的成员函数 handleLaunchActivity 来启动由 ActivityClientRecord 对象所描述的一个 Activity 组件，即 MainActivity 组件。

```java
public void handleMessage(Message msg) {
    if (DEBUG_MESSAGES) Slog.v(TAG, ">>> handling: " + msg.what);
    switch (msg.what) {
        case LAUNCH_ACTIVITY: {
            ActivityClientRecord r = (ActivityClientRecord)msg.obj;

            r.packageInfo = getPackageInfoNoCheck(
                    r.activityInfo.applicationInfo);
            handleLaunchActivity(r, null);
        } break;
        //...
    }
    //...
}
```

### Step33 ActivityThread.handleLaunchActivity

首先调用成员函数 performLaunchActivity 将 MainActivity 组件启动起来，接着调用成员函数 handleResumeActivity 将 MainActivity 组件的状态设置为 Resumed，表示它是系统当前激活的 Activity 组件。

```java
    private final void handleLaunchActivity(ActivityClientRecord r, Intent customIntent) {
        //...
        Activity a = performLaunchActivity(r, customIntent);

        if (a != null) {
            r.createdConfig = new Configuration(mConfiguration);
            Bundle oldState = r.state;
            handleResumeActivity(r.token, false, r.isForward);
            //..
        }
        //...
    }
```

### Step34 ActivityThread.performLaunchActivity

首先获取需要启动的 Activity 的包名和类名，保存在一个结构 ComponentName 中。

随后将这个类加载到内存中，并创建一个实例，保存在 activity 这个变量中。

然后创建和初始化了一个 ContextImpl 对象 appContext，用来作为前面所创建的 Activity 对象 activity 的运行上下文环境，通过它就可以访问到特定的应用程序资源，以及启动其他的应用程序组件。接着使用 ContextImpl 对象 appContext 和 ActivityClientRecord 对象 r 来初始化 Activity 对象 activity。

Activity 对象 activity 初始化完成之后，就调用成员变量 mInstrumentation 的成员函数 callActivityOnCreate 将 Activity 对象 activity 启动起来。在这个过程中，Activity 对象 activity 的成员函数 onCreate 就会被调用。

Activity 对象 activity 启动完成之后，就会以 ActivityClientRecord 对象 r 的成员变量 token 为关键字，将 ActivityClientRecord 对象 r 保存在 ActivityThread 类的成员变量 mActivities 中。

```java
    private final Activity performLaunchActivity(ActivityClientRecord r, Intent customIntent) {
        // System.out.println("##### [" + System.currentTimeMillis() + "] ActivityThread.performLaunchActivity(" + r + ")");

        //...
        ComponentName component = r.intent.getComponent();
        //...

        Activity activity = null;
        try {
            java.lang.ClassLoader cl = r.packageInfo.getClassLoader();
            activity = mInstrumentation.newActivity(
                    cl, component.getClassName(), r.intent);
            //...
        } catch (Exception e) {
            //...
        }

        try {
            Application app = r.packageInfo.makeApplication(false, mInstrumentation);
            //...

            if (activity != null) {
                ContextImpl appContext = new ContextImpl();
                appContext.init(r.packageInfo, r.token, this);
                appContext.setOuterContext(activity);
                CharSequence title = r.activityInfo.loadLabel(appContext.getPackageManager());
                Configuration config = new Configuration(mConfiguration);
                //...
                activity.attach(appContext, this, getInstrumentation(), r.token,
                        r.ident, app, r.intent, r.activityInfo, title, r.parent,
                        r.embeddedID, r.lastNonConfigurationInstance,
                        r.lastNonConfigurationChildInstances, config);

                //...
                mInstrumentation.callActivityOnCreate(activity, r.state);
                //...
            }
            r.paused = true;

            mActivities.put(r.token, r);

        } catch (SuperNotCalledException e) {
            throw e;

        } catch (Exception e) {
            //...
        }

        return activity;
    }
```

