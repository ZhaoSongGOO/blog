## Native 访问 Java


```java
class Hello {
    public static String Name;
    public String mSubName;

    public static String GetString(String str){
        //... do something
    }

    public void Calc(int a, int b){
        // ... do something
    }

    private native access_instance_member();
    private static native access_class_member();
    private native access_instance_function();
    private static native access_class_function();
}
```

### 访问成员变量

#### 访问实例变量

```c
extern "C"
JNIEXPORT void JNICALL
Java_Hello_access_instance_member(JNIEnv *env, jobject obj) {
    jclass clazz;
    jfieldID mString_fieldID;

    clazz = env->GetObjectClass(obj);

    if (clazz == NULL) {
        return;
    }

     mString_fieldID = env->GetFieldID(clazz, "mSubName", "Ljava/lang/String;");
    if (mString_fieldID == NULL) {
        return;
    }

    jstring j_string = (jstring) env->GetObjectField(obj, mString_fieldID);
    const char *buf = env->GetStringUTFChars(j_string, NULL);

    char *buf_out = "Hello Java!";
    jstring temp = env->NewStringUTF(buf_out);
    env->SetObjectField(obj, mString_fieldID, temp);

    env->ReleaseStringUTFChars(j_string, buf);
    env->DeleteLocalRef(j_string);
    env->DeleteLocalRef(clazz);
}

```


#### 访问静态变量

```c
extern "C"
JNIEXPORT void JNICALL
Java_Hello_access_class_member(JNIEnv *env, jclass clazz) {
    jfieldID mStaticIntFiledID;
    mStaticIntFiledID = env->GetStaticFieldID(clazz, "Name", "Ljava/lang/String;");
    jint mInt = env->GetStaticIntField(clazz, mStaticIntFiledID);
    env->SetStaticIntField(clazz, mStaticIntFiledID, "Hello, I have change you!");
    env->DeleteLocalRef(clazz);  
}

```

### 访问方法


#### 访问实例方法

```c
extern "C"
JNIEXPORT void JNICALL
Java_Hello_access_instance_function(JNIEnv *env, jobject thiz) {

    jclass clazz ;

    clazz = env->GetObjectClass(thiz);

    if (clazz == NULL) {
        return;
    }

    jmethodID java_method_id = env->GetMethodID(clazz, "Calc", "(II)V");
    if (java_method_id == NULL) {
        return;
    }

    env->CallVoidMethod(thiz,java_method_id);
    env->DeleteLocalRef(clazz);
    env->DeleteLocalRef(object_test);
}


```

#### 访问静态方法

```c

extern "C"
JNIEXPORT void JNICALL
Java_Hello_access_class_function(JNIEnv *env, jclass clazz) {
    jmethodID static_method_id = env->GetStaticMethodID(clazz, "GetString", "(Ljava/lang/String;)Ljava/lang/String;");
    if(NULL == static_method_id)
    {
        return;
    }
    env->CallStaticVoidMethod(clazz, static_method_id);
    env->DeleteLocalRef(clazz);
}


```