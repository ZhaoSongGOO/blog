# 广播接收者的注册

首先我们看一下一个广播接收者是如何定义与注册的，这里我们只考虑动态注册。

```java
class TimerReceiver : BroadcastReceiver() {
    override fun onReceive(
        context: Context?,
        intent: Intent?,
    ) {
        Toast.makeText(context, LionConstants.LION_TAG + ": TimerReceiver", Toast.LENGTH_LONG).show()
    }
}

val timeReceiver = TimerReceiver()
val intent = IntentFilter("android.intent.action.TIME_TICK")
registerReceiver(timeReceiver, intent)

```

## Step1: ContextWrapper.registerReceiver
## Step2: ContextImpl.registerReceiver

这里和 service 的启动过程一样，首先使用 getReceiverDispatcher 将传入的 receiver 进行包装，封装成一个 binder 本地对象 IIntentReceiver，为的是后续可以进行跨进程通信。

随后使用 AMS 的 registerReceiver 接口进行跨进程注册。

```java
    @Override
    public Intent registerReceiver(BroadcastReceiver receiver, IntentFilter filter) {
        return registerReceiver(receiver, filter, null, null);
    }

    @Override
    public Intent registerReceiver(BroadcastReceiver receiver, IntentFilter filter,
            String broadcastPermission, Handler scheduler) {
        return registerReceiverInternal(receiver, filter, broadcastPermission,
                scheduler, getOuterContext());
    }

    private Intent registerReceiverInternal(BroadcastReceiver receiver,
            IntentFilter filter, String broadcastPermission,
            Handler scheduler, Context context) {
        IIntentReceiver rd = null;
        if (receiver != null) {
            if (mPackageInfo != null && context != null) {
                if (scheduler == null) {
                    scheduler = mMainThread.getHandler();
                }
                rd = mPackageInfo.getReceiverDispatcher(
                    receiver, context, scheduler,
                    mMainThread.getInstrumentation(), true);
            } else {
                if (scheduler == null) {
                    scheduler = mMainThread.getHandler();
                }
                rd = new LoadedApk.ReceiverDispatcher(
                        receiver, context, scheduler, null, true).getIIntentReceiver();
            }
        }
        try {
            return ActivityManagerNative.getDefault().registerReceiver(
                    mMainThread.getApplicationThread(),
                    rd, filter, broadcastPermission);
        } catch (RemoteException e) {
            return null;
        }
    }
```

## Step3: ActivityManagerService.registerReceiver

首先根据参数 caller 得到一个 ProcessRecord 对象 callerApp，用来描述正在请求 ActivityManagerService 注册广播接收者的一个 Activity 组件所运行在的应用程序进程。

在 ActivityManagerService 中，每一个广播接收者都是使用一个 BroadcastFilter 对象来描述的，而每一个 BroadcastFilter 对象又是根据它所描述的广播接收者所关联的一个 InnerReceiver 对象，以及所要接收的广播的类型来创建的。由于在一个应用程序中，不同的 Activity 组件可能会使用同一个 InnerReceiver 对象来注册不同的广播接收者，因此，ActivityManagerService 就会使用一个 ReceiverList 列表来保存这些使用了相同 InnerReceiver 对象来注册的广播接收者，并且以它们所使用的 InnerReceiver 对象为关键字。



```java
    public Intent registerReceiver(IApplicationThread caller,
            IIntentReceiver receiver, IntentFilter filter, String permission) {
        synchronized(this) {
            ProcessRecord callerApp = null;
            if (caller != null) {
                callerApp = getRecordForAppLocked(caller);
                //...
            }
            //...

            ReceiverList rl
                = (ReceiverList)mRegisteredReceivers.get(receiver.asBinder());
            if (rl == null) {
                rl = new ReceiverList(this, callerApp,
                        Binder.getCallingPid(),
                        Binder.getCallingUid(), receiver);
                //...
                mRegisteredReceivers.put(receiver.asBinder(), rl);
            }
            BroadcastFilter bf = new BroadcastFilter(filter, rl, permission);
            rl.add(bf);
            //...
            mReceiverResolver.addFilter(bf);
            //...
            return sticky;
        }
    }
```
