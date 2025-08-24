# 基础能力

什么是基础能力问题，这类问题没有复杂的讨论，不涉及什么递归，贪心等算法概念，纯粹的考察数据结构基础功力以及设计能力。

## [两数相加](https://leetcode.cn/problems/add-two-numbers/description/)

题目给了我们两个非空链表，各自代表一个整数的逆序，让我们将这个两个数相加，返回一个表示和的链表。

1. Don't code! Think!

思考一下，两个数相加，我们从只需要从低位开始相加，逐步向高位移动，如果有进位，高位需要额外的考虑进位。看起来没什么难度。

我们是考虑构建一个新的链表承载结果值呢，还是在原有的其中一个链表上直接修改。

同时还需要考虑的是，如果一个链表结束了，另外一个链表还没结束，我们如何处理后面进位与其的交互。


## [Z 字形变换](https://leetcode.cn/problems/zigzag-conversion/description/)

这个就是一个单纯的边界考察题。

我们需要记住每一行的字符内容，最后进行拼接即可。

在第一列，当从上到下的时候，每个字符落的行数是 从 0 开始增加到 numRows - 1;

随后折返，从下到上的时候，行数从 numRows - 2 到 0;

随后再次折返，从上到下，行数从 1 到 numRows - 1;

随后折返，从下到上的时候，行数从 numRows - 2 到 0;

...

我们只需要控制行数的变化以及起始值即可。

```cpp
  string convert(string s, int numRows) {
    if(numRows == 1){
        return s;
    }
    std::vector<std::string> vs(numRows);
    bool down = true;
    int line = 0;
    for(int index = 0; index < s.size(); index++){
        vs[line].push_back(s[index]);
        if(down){
            line++;
        }else{
            line--;
        }

        if(line == numRows){
            line -= 2;
            down = false;
        }
        if(line == -1){
            down = true;
            line += 2;
        }
    }

    std::string re_str = "";
    for(auto p: vs){
        re_str += p;
    }
    return  re_str;
}
```

## [整数反转](https://leetcode.cn/problems/reverse-integer/description/)

给你一个 32 位的有符号整数 x ，返回将 x 中的数字部分反转后的结果。

没什么难点，主要就是考察你如何将一个数据按照每位拆分出来，以及边界条件的考察。


