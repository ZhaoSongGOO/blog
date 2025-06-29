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

## ViewFlipper

ViewFlipper 是 Android 提供的一个用于在多个视图之间切换的控件，适合实现图片轮播、引导页、广告切换等场景。它内部其实就是一个 ViewGroup，每次只显示其中的一个子 View，通过动画切换来达到“翻页”的效果。

### 使用

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:orientation="vertical"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <ViewFlipper
        android:id="@+id/viewFlipper"
        android:layout_width="match_parent"
        android:layout_height="200dp">
        <ImageView
            android:src="@drawable/app_icon"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:scaleType="centerCrop"/>
        <ImageView
            android:src="@drawable/ic_launcher_foreground"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:scaleType="centerCrop"/>
        <ImageView
            android:src="@drawable/ic_launcher_background"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:scaleType="centerCrop"/>
    </ViewFlipper>

</LinearLayout>
```

```kotlin
class ViewFlipperActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_view_flipper)
        val viewFlipper = findViewById<ViewFlipper>(R.id.viewFlipper)
        viewFlipper.flipInterval = 2000 // 2秒切换
        viewFlipper.isAutoStart = true
        // 设置动画
        viewFlipper.inAnimation = AnimationUtils.loadAnimation(this, android.R.anim.fade_in)
        viewFlipper.outAnimation = AnimationUtils.loadAnimation(this, android.R.anim.fade_out)
        // 开始轮播
        viewFlipper.startFlipping()
    }
}
```

## RecyclerView

相比于 ListView，RecyclerView 具有如下的优势：

<img src="android/interview/ui/scroll/resources/1.png" style="width:80%">

### 使用

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:orientation="vertical"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:id="@+id/root">

    <androidx.recyclerview.widget.RecyclerView
        android:id="@+id/recyclerView"
        android:layout_width="match_parent"
        android:layout_height="match_parent"/>

</LinearLayout>
```

自定义 Adapter。

```kotlin
class MainPageRecycleViewAdapter(private val items: List<ListItem>, private val onItemClick: (ListItem) -> Unit) :
    RecyclerView.Adapter<MainPageRecycleViewAdapter.ViewHolder>() {
    inner class ViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        val title: TextView = itemView.findViewById(R.id.itemTitle)
        val description: TextView = itemView.findViewById(R.id.itemDescription)

        init {
            itemView.setOnClickListener {
                val position = adapterPosition
                if (position != RecyclerView.NO_POSITION) {
                    onItemClick(items[position])
                }
            }
        }
    }

    override fun onCreateViewHolder(
        parent: ViewGroup,
        viewType: Int,
    ): ViewHolder {
        val view =
            LayoutInflater.from(parent.context)
                .inflate(R.layout.main_page_list_item, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(
        holder: ViewHolder,
        position: Int,
    ) {
        val item = items[position]
        holder.title.text = item.title
        holder.description.text = item.description
    }

    override fun getItemCount() = items.size
}
```

Activity 中配置 RecycleView.

```kotlin
class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        val recyclerView = findViewById<RecyclerView>(R.id.recyclerView)

        recyclerView.layoutManager = LinearLayoutManager(this)

        val adapter =
            MainPageRecycleViewAdapter(MainPageData.ITEMS) { item ->
                val intent = Intent(this, item.activity)
                startActivity(intent)
            }

        recyclerView.adapter = adapter
    }
}
```

## SwipeRefreshLayout

## DrawerLayout

## ViewPager


