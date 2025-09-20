# 子Activity组件在进程内的启动过程

---

MainActivity 组件启动 SubActivityInProcess 组件的过程如下所示。

1. MainActivity 组件向 AMS 发送一个启动 SubActivityInProcess 组件的进程间通信请求。

2. AMS 首先将要启动的 SubActivityInProcess 组件的信息保存下来，然后再向 MainActivity 组件发送一个进入中止状态的进程间通信请求。

3. MainActivity 组件进入到中止状态之后，就会向 AMS 发送一个已进入中止状态的进程间通信请求，以便 AMS 可以继续执行启动 SubActivityInProcess 组件的操作。

4. AMS 发现用来运行 SubActivityInProcess 组件的应用程序进程已经存在，因此它就会将第2步保存下来的 SubActivityInProcess 组件信息发送给该应用程序进程，以便它可以将 SubActivityInProcess 组件启动起来。由于 AMS 不需要创建一个新的应用程序进程来启动 SubActivityInProcess 组件，因此，SubActivityInProcess 组件的启动过程要比 MainActivity 组件的启动过程简单一些，一共分为 30 个步骤。接下来，我们就详细分析每一个步骤。

---

## Step1 MainActivity.onClick

设想这样的一个场景，我们在 MainActivity 中点击一个按钮，在这个按钮的点击事件回调中启动 SubActivityInProcess。

然后使用 SubActivityInProcess 的 action 构造 intent，并使用 startActivity 方法来启动这个 activity。

```java
Intent intent = new Intent("subactivity.in.process");
startActivity(intent);
```

## Step2 Activity.startActivity
## Step3 Activity.startActivityForResult
## Step4 Instrumentation.execStartActivity
## Step5 ActivityManagerProxy.startActivity
## Step6 ActivityManagerService.startActivity
## Step7 ActivityStack.startActivityMayWait
## Step8 ActivityStack.startActivityLocked

## Step9 ActivityStack.startActivityUncheckedLocked

ActivityRecord 对象 r 用来描述即将要启动的 SubActivityInProcess 组件，而 ActivityRecord 对象 sourceRecord 用来描述请求 ActivityManagerService 启动 SubActivityInProcess 组件的 MainActivity 组件。

在前面的 Step1 中，由于 MainActivity 组件没有指定要在新的任务中启动 SubActivityInProcess 组件，并且 MainActivity 组件和 SubActivityInProcess 组件的 android:taskAffinity 属性都是一样的，即 ActivityManagerService 不需要创建一个新的任务来启动 SubActivityInProcess 组件，因此，就会将 ActivityRecord 对象 sourceRecord 的成员变量 task 的值赋给 ActivityRecord 对象 r 的成员变量 task，表示 SubActivityInProcess 组件和 MainActivity 组件是运行在同一个任务中的。

```java
    final int startActivityUncheckedLocked(ActivityRecord r,
            ActivityRecord sourceRecord, Uri[] grantedUriPermissions,
            int grantedMode, boolean onlyIfNeeded, boolean doResume) {
        //...
        
        int launchFlags = intent.getFlags();
        
        //...

        boolean addingToTask = false;
        //...

        boolean newTask = false;

        // Should this be considered a new task?
        // 这个 if 语句是 false 的
        if (r.resultTo == null && !addingToTask
                && (launchFlags&Intent.FLAG_ACTIVITY_NEW_TASK) != 0) {
            //...
        // 进入这个 if 语句
        } else if (sourceRecord != null) {
            //...
            r.task = sourceRecord.task;
            //...
        } else {
            //...
        }
        //...
        startActivityLocked(r, newTask, doResume);
        return START_SUCCESS;
    }
```

在 startActivityLocked 方法中。前面传进来的参数 newTask 的值等于 false，因此，for 循环首先在 Activity 组件堆栈 mHistory 中找到一个合适的位置 addPos，接着可以将参数 r 所描述的 SubActivityInProcess 组件保存在这个位置中。

```java
    private final void startActivityLocked(ActivityRecord r, boolean newTask,
            boolean doResume) {
        final int NH = mHistory.size();

        int addPos = -1;
        
        if (!newTask) {
            // If starting in an existing task, find where that is...
            boolean startIt = true;
            for (int i = NH-1; i >= 0; i--) {
                ActivityRecord p = (ActivityRecord)mHistory.get(i);
                if (p.finishing) {
                    continue;
                }
                if (p.task == r.task) {
                    // Here it is!  Now, if this is not yet visible to the
                    // user, then just add it without starting; it will
                    // get started when the user navigates back to it.
                    addPos = i+1;
                    //...
                    break;
                }
                //...
            }
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

我们知道，在 AMS 中，已经启动的 Activity 组件是以任务为单位组织在 Activity 组件堆栈 mHistory 中的，即同一个任务中的所有 Activity 组件都是连在一起的。

<img src="android/framework/app_framework/activity_launch/resources/5.png" style="width:20%">

Activity1.1 和 Activity1.2 是属于任务 Task1 的，而 Activity2.1 和 Activity2.2 是属于任务 Task2 的，其中，Activity1.2 和 Activity2.2 分别是被 Activity1.1 和 Activity2.1 启动起来的；因此，Activity1.2 位于 Activity1.1 的上面，而 Activity2.2 位于 Activity2.1 的上面。

---

随后 AMS 会通知原进程暂停当前 Activity，原进程在暂停后，又会发送 activityPaused 给 AMS。

## Step10 ActivityStack.resumeTopActivityLocked
## Step11 ActivityStack.startPausingLocked
## Step12 ApplicationThreadProxy.schedulePauseActivity
## Step13 ApplicationThread.schedulePauseActivity
## Step14 ActivityThread.queueOrSendMessage
## Step15 H.handleMessage
## Step16 ActivityThread.handlePauseActivity
## Step17 ActivityManagerProxy.activityPaused

---

然后呢，收到暂停消息后，开始准备启动目标 Activity。

## Step18 ActivityManagerService.activityPaused
## Step19 ActivityStack.activityPaused
## Step20 ActivityStack.completePauseLocked
## Step21 ActivityStack.resumeTopActivityLokced

---

## Step22 ActivityStack.startSpecificActivityLocked

参数 r 所描述的 Activity 组件即为 SubActivityInProcess 组件，这个 r 和 MainActivity 运行在同一个进程，既然 MainActivity 已经启动成功了，那 r.app 以及 app.thread 肯定不是为空的，所以直接调用 realStartActivityLocked 启动目标 SubActivityInProcess。

```java
    private final void startSpecificActivityLocked(ActivityRecord r,
            boolean andResume, boolean checkConfig) {
        // Is this activity's application already running?
        ProcessRecord app = mService.getProcessRecordLocked(r.processName,
                r.info.applicationInfo.uid);
        
        //...
        
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
        //...
    }
```

--- 

## Step23 ActivityStack.realStartActivityLocked
## Step24 ApplicationThreadProxy.scheduleLaunchActivity
## Step25 ApplicationThread.scheduleLaunchActivity
## Step26 ActivityThread.queueOrSendMessage
## Step27 H.handleMessage
## Step28 ActivityThread.handleLaunchActivityStep 
## Step29 ActivityThread.performLaunchActivity
---

