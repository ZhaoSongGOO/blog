## 异常处理

> :hourglass: JNI 异常分为三种
> 1. c 中的异常，触发系统的异常处理逻辑，例如 SIGKILL, SIGAbort.
> 2. JNIEnv 执行过程的异常，在 c 中通过对执行返回值判断，有异常直接 return，异常会返回到 java 层中被处理。
> 3. native 调用 java 方法后，java 方法中触发的异常。
> 
我们这里只对第三种做说明。

### native 直接返回

变成第二种情况，由 java 层进行处理。

### native 处理再返回

如果异常和 native 相关，那我们可以在 native 中对异常进行处理。

```c
env->CallStaticIntMethod(clazz, static_method_id);
jthrowable mThrowable;

if (env->ExceptionCheck()) {
    mThrowable = env->ExceptionOccurred();
    env->ExceptionDescribe();
    //清除异常信息
    //如果，异常还需要 Java 层处理，可以不调用 ExceptionClear，让异常传递给 Java 层
    env->ExceptionClear();
    //如果调用了 ExceptionClear 后，异常还需要 Java 层处理，我们可以抛出一个新的异常给 Java 层
    jclass clazz_exception = env->FindClass("java/lang/Exception");
    env->ThrowNew(clazz_exception, "JNI抛出的异常！");
    env->DeleteLocalRef(clazz_exception);
}
```






