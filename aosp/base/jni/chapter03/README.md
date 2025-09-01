## 如何在 native 中找到 java 中的属性


> :hourglass: JNI 使用特殊的字符串格式来表示 java 中的属性。


### 类

使用其全部包名来表示一个类，并对其中的 '.' 替换成 '/'

```java
java.lang.String

java/lang/String

```

### 类型

| 符号  | 类型  |
|------| ------|
| Z    | boolean|
| B    | byte   |
| C | char |
|S | short |
| I | int |
|J | long |
|F | float|
|D | double |
|L类描述符 | 各种引用类型|
| V    | void |
| [    | 数组 |
| (ABC)D | 函数 |

### 函数

``` java

String func()    ()Ljava/lang/String;
int func(int i, String s)  (ILjava/lang/String;)I
void func(String a, String[] b)  (Ljava/lang/String;[L/java/lang/String;)V
```



