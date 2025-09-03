## JNI 数据类型

> :hourglass: jni 本质是数据类型的转换器，在 java 调用 native 方法时候，无非就是下面的流程：
> 1. jni 将 java 类型转换成 jni 数据类型。
> 2. native 方法收到 jni 数据类型，进行自己的运算，生成结果 c 类型。
> 3. c 类型包装成 jni 类型返回。
> 4. jni 将 jni 类型转换成 java 类型交给 java 方法。

### 数据类型定义
#### 基本数据类型

因为这些数据类型本质就是基础的 c 数据类型，因此可以在 c 中直接使用。
```c
// jni.h
typedef unsigned char   jboolean;
typedef unsigned short  jchar;
typedef short           jshort;
typedef float           jfloat;
typedef double          jdouble;
typedef jint            jsize;

typedef int jint;
#ifdef _LP64
typedef long jlong;
#else
typedef long long jlong;
#endif

typedef signed char jbyte;

```

#### 引用数据类型

引用类型本质都是 jobject 派生而来，其内部做了数据的封装，因此我们要想使用，必须进行转换才行。

```c
struct _jobject;

typedef struct _jobject *jobject;
typedef jobject jclass;
typedef jobject jthrowable;
typedef jobject jstring;
typedef jobject jarray;
typedef jarray jbooleanArray;
typedef jarray jbyteArray;
typedef jarray jcharArray;
typedef jarray jshortArray;
typedef jarray jintArray;
typedef jarray jlongArray;
typedef jarray jfloatArray;
typedef jarray jdoubleArray;
typedef jarray jobjectArray;
```

### 对象创建与销毁

对于 c 使用 malloc 或者 new 创建的对象，需要使用 delete 或者 free 去进行释放。
对于创建的 jobject 对象，在生命周期上类似于 java 对象，统一由 jvm 的 gc 系统来进行管理。具体方式取决于 jobject 的类型。

#### 局部引用

##### 如何创建局部引用

1. JNI 接口传递下来的引用类型为局部引用。
2. 通过 NewLocalRef 构造的引用类型为局部引用。
3. 通过各种 JNI 接口创建的引用为局部引用。(FindClass、 NewObject...)

##### 局部引用特点

1. 在函数执行完成前，局部引用不会被 GC。
2. 函数返回时，局部引用会被 JVM 自动释放，也可以使用 DeleteLocalRef 手动释放。
3. 如果函数返回的是局部引用本身，java 层会对其增加一个引用，在 java 层对象不用的时候，才会回收这个局部引用。
4. 每一个 native 方法创建局部引用的数目是有限制的。


#### 全局引用

##### 如何创建全局引用

1. 使用 NewGlobalRef 来创建。

##### 特点

1. 全局引用不会被 GC，除非手动 DeleteGlobalProf。

#### 弱全局引用

##### 如何创建全局弱引用

1. 使用 NewWeakGlobalRef 创建对一个对象的全局弱引用。

##### 特点

1. 全局弱引用一般绑定在一个已经创建好的全局引用上。
2. 全局弱引用不会阻止 GC，因此我们需要再使用前判断绑定的对象是否已经被回收。

### 关于 JNI 中数据类型生命周期管理

我觉得在 jni 开发中，一个关键的要素在于变量的生命周期管理，这个对于代码健壮性至关重要。

通过 jni 接口生成的数据一般有这样三种类型的变量:

#### 引用类型

引用类型就是 jobject 以及继承自 jobject 的各种数据类型，我们通过 jni 各种函数返回 jobject 类型都属于引用类型，引用类型的生命周期就是前面介绍的本地引用和全局引用。

这种数据类型本质是一个 c 侧的引用，实际数据位于 jvm 中，这个 c 侧的引用会增加 jvm 中对象的引用计数。

#### 堆类型数据

使用 jni `GetXXX` 函数返回的数据类型是 jint * 或者 char * 类似类型的数据，这些数据是 jvm 将内部的数据先做一次拷贝/转换，存储在堆区，随后返回的堆区的指针。这部分数据不会被 gc 系统管理，如果不释放会直接导致内存泄漏。

所以我们在使用后需要进行 `ReleaseXXX` 的释放操作。

```c
jstring label_java_string = (jstring)env->GetObjectField(obj, label_id);
if (label_java_string == nullptr) {
    return;
}

const char *buf = env->GetStringUTFChars(label_java_string, nullptr);


env->ReleaseStringUTFChars(label_java_string, buf);
```


#### 栈类型数据

对于我们使用 jni 的 GetXXX 返回的是 jsize, jint 这样的值，那这就是一个纯粹的栈或者寄存器数据，无需其释放。

```c
jsize size = env->GetArrayLength(arr);
```



