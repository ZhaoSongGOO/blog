## 字符串和数组访问

### 字符串

JNI 把 java 中的 String 对象包装在 jstring 引用类型中传递下去，我们如果现在 c 中直接获取 jstring 中的内容, 需要通过 JNIEnv 来操作。同理如果我们需要从一个 c 风格的字符串生成 jstring，也需要用过 JNIEnv 来进行操作。

```c
// 一般都会返回副本，而不是原始字符串指针。
const char* cStr = env->GetStringUTFChars(str, &isCopy);

// 这里必须要进行 release，因为拿到的 cStr 存储在 JVM 中，如果我们不显示调用，那就会导致内存泄漏。
env->ReleaseStringUTFChars(str, cStr);

const char * result = "hello";
jstring v = env->NewStringUTF(result);
```

#### GetStringCritical 和 ReleaseStringCritical

相比于其他的方法，这对方法会直接获取 jstring 指向的 java 字符串的指针，而不是返回副本。这在大尺寸字符串操作的时候可以有效的提高效率。
但是有一个要求，就是在 这对函数之间不可以做任何让线程阻塞的操作，因为当 c 获取到 java 中的原生指针的时候，会暂停 GC 线程。其余的线程在触发 GC 后都会被阻塞。
如果此时调用 GetStringCritical 的这段逻辑，也阻塞 (依赖其余线程的操作) 那就会出现互持等待死锁。


### 数组

#### 访问基础类型数组
直接转换，转成对应的 native 类型的数组。

```c
JNIEXPORT jdoubleArray JNICALL Java_HelloJNI_sumAndAverage(JNIEnv *env, jobject obj, jintArray inJNIArray) {
    jboolean isCopy;
    jint* inArray = env->GetIntArrayElements(inJNIArray, &isCopy);
    jsize length = env->GetArrayLength(inJNIArray);
    env->ReleaseIntArrayElements(inJNIArray, inArray, 0); 
    jdouble outArray[] = {1, 2};
    jdoubleArray outJNIArray = env->NewDoubleArray(2);
    env->SetDoubleArrayRegion(outJNIArray, 0, 2, outArray);
    return outJNIArray;
}

```


#### 访问对象类型数组
遍历访问，需要对每一个元素单独操作。

```c
JNIEXPORT jobjectArray JNICALL Java_com_xxx_jni_JNIArrayManager_operateStringArrray
  (JNIEnv * env, jobject object, jobjectArray objectArray_in)
{
    jsize  size = env->GetArrayLength(objectArray_in);

	for(int i = 0; i < size; i++)
	{
		jstring string_in= (jstring)env->GetObjectArrayElement(objectArray_in, i);
        char *char_in  = env->GetStringUTFChars(str, nullptr);
	}

	jclass clazz = env->FindClass("java/lang/String");
	jobjectArray objectArray_out;
	const int len_out = 5;
	objectArray_out = env->NewObjectArray(len_out, clazz, NULL);
	char * char_out[]=  { "Hello,", "world!" };

	jstring temp_string;
	for( int i= 0; i < len_out; i++ )
    {   
        temp_string = env->NewStringUTF(char_out[i])；
        env->SetObjectArrayElement(objectArray_out, i, temp_string);
    }
	return objectArray_out;
}



```



