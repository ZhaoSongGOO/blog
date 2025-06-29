# 可滑动组件

## ScrollView & HorizontalScrollView

### 如何使用

ScrollView 最为简单，其会在内部元素尺寸超出自身尺寸时，让内部元素可以滚动。

```xml
<ScrollView
    android:id="@+id/scrollView"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:padding="16dp"
    android:background="@drawable/green_shape">

    <LinearLayout
        android:id="@+id/container"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="vertical">
    </LinearLayout>
</ScrollView>
```

### 处理滚动事件

```kotlin
scrollView.viewTreeObserver.addOnScrollChangedListener {
    val scrollY = scrollView.scrollY
    scrollInfo.text = "当前滚动位置: ${scrollY}px"
}
```


## ListView

### 使用方式

ListView 相比于 ScrollView, 就更为科学，其实现了视图与内容的分离，两者之间通过 Adapter 来进行衔接。如果想给 ListView 中的数据增加内容，只需要在 Adapter 中增加数据即可。

```kotlin
class ListViewDemoActivity : Activity() {
    data class MyItem(val title: String, val desc: String)

    class MyAdapter(context: Context, val resourceId: Int, objects: List<MyItem>) : ArrayAdapter<MyItem>(context, resourceId, objects) {
        override fun getView(
            position: Int,
            convertView: View?,
            parent: ViewGroup,
        ): View {
            val view = LayoutInflater.from(context).inflate(resourceId, parent, false)
            val item = getItem(position)
            item?.let {
                view.findViewById<TextView>(R.id.itemTitle).text = it.title
                view.findViewById<TextView>(R.id.itemDescription).text = it.desc
            }
            return view
        }

        override fun getCount(): Int {
            return super.getCount()
        }
    }

    var data = mutableListOf<MyItem>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_listview)

        val listView = findViewById<ListView>(R.id.container)
        val button = findViewById<Button>(R.id.add)
        val adapter = MyAdapter(this, R.layout.main_page_list_item, data)
        listView.adapter = adapter

        button.setOnClickListener {
            data.add(MyItem("1", "2"))
            adapter.notifyDataSetChanged()
        }

        listView.setOnItemClickListener(
            object : OnItemClickListener {
                override fun onItemClick(
                    parent: AdapterView<*>?,
                    view: View?,
                    position: Int,
                    id: Long,
                ) {
                    val item: String? = data[position].desc
                    Toast.makeText(view?.context, "你点击了: " + item, Toast.LENGTH_SHORT).show()
                }
            },
        )
    }
}

```

## GridView


## SeekBar

SeekBar 是 Android 中常用的滑动条控件，常用于音量调节、进度选择等场景

### 使用

```xml
<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <SeekBar
        android:layout_width="300dp"
        android:layout_height="wrap_content"
        android:max="100"
        android:layout_gravity="center"
        android:id="@+id/seek"/>

</FrameLayout>
```

```kotlin
class SeekBarDemoActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_seekbar)
        findViewById<SeekBar>(R.id.seek).setOnSeekBarChangeListener(
            object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(
                    seekBar: SeekBar?,
                    progress: Int,
                    fromUser: Boolean,
                ) {
                    Toast.makeText(seekBar?.context, "当前进度：$progress", Toast.LENGTH_SHORT).show()
                }

                override fun onStartTrackingTouch(seekBar: SeekBar?) {
                    // 用户开始拖动时触发
                }

                override fun onStopTrackingTouch(seekBar: SeekBar?) {
                    // 用户结束拖动时触发
                }
            },
        )
    }
}

```

## ViewPager

## SlidingMenu


## RecyclerView

## ViewFlipper

## Android-PullToRefresh

