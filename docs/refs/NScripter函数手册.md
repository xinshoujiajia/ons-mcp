---
title: NScripter函数手册
date: 2023-04-22 16:25:38
tags: 
- ONS
---

之前记录的NScripter的函数手册，配合NScripter语法食用。

<!--more-->

## 函数分类表

| 类别               | 描述                                         |
|--------------------|----------------------------------------------|
| Predefined Syntax  | 具有预定义函数的关键字或标签                 |
| F Commands         | 只能在定义块中使用的命令                     |
| E Commands         | 只能在语句块中使用的命令                     |
| F/E Commands       | 可以在语句或定义块中使用的命令               |
| Special Characters | 可以在显示的文本块中用作命令替代品的特殊字符 |

### 游戏的开始/重置/退出

| 命令        | 类别 | 描述                 |
|-------------|------|----------------------|
| [*define](#*define)     | P    | 表示定义块开始的标签 |
| [*start](#*start)      | P    | 表示语句块开始的标签 |
| [game](#game)        | E    | 结束定义块和执行游戏 |
| [reset](#reset)       | F    | 重置游戏             |
| [definereset](#definereset) | F    | 强制全部脚本重置     |
| [end](#end)         | E/F  | 结束游戏并关闭窗口   |

### 语法标记

| 命令 | 类别 | 描述                       |
|------|------|----------------------------|
| [*](#*)    | P    | 标签的前缀                 |
| [;](#;)    | P    | 描述的前缀                 |
| [:](#:)    | P    | 在一行上写入和执行多个命令 |
| [%](#%)    | P    | 数字变量的前缀             |
| [\$](#\$)    | P    | 字符变量的前缀             |
| [?](#?)    | P    | 数组变量的前缀             |
| [~](#~)    | P    | jumpf/jumpb的目标点        |
| [\`](#\`)    | S    | 允许1字节字符显示          |
| [/](#/)    | S    | 忽略换行                   |
### 文本框

| 命令            | 描述                       |
|-----------------|----------------------------|
| [setwindow](#setwindow)       | 设置文本窗口和字符显示属性 |
| [setwindow2](#setwindow2)      | 修改文本窗口外观           |
| [textoff](#textoff)         | 隐藏文本窗口               |
| [texton](#texton)          | 显示文本窗口               |
| [windoweffect](#windoweffect)    | 为文本窗口指定特效         |
| [erasetextwindow](#erasetextwindow) | 在特效运行时切换文本显示   |
### 文本显示

| 命令        | 描述                                       |
|-------------|--------------------------------------------|
| [defaultfont](#defaultfont) | 指定默认字体                               |
| [!s](#!s)          | 指定字符显示速度                           |
| [#](##)           | 更改字符颜色                               |
| [textclear](#textclear)   | 清除显示的文本                             |
| [locate](#locate)      | 在不更改文本窗口位置的情况下更改字符的位置 |
| [puttext](#puttext)     | 写下一些小指示（例如，在语句之后）         |
| [br](#br)          | 在显示的文本中插入回车                     |
| [textspeed](#textspeed)   | 更改文本显示速度                           |
### 点击等待

| 命令       | 描述                                         |
|------------|----------------------------------------------|
| [@](#@)          | 进入点击等待状态                             |
| [\\](#\\)          | 进入回车等待状态                             |
| [clickstr](#clickstr)   | 点击指定字符串时输入单击等待状态             |
| [_](#_)          | 忽略下一次点击                               |
| [linepage](#linepage)   | 等待行尾的点击                               |
| [clickvoice](#clickvoice) | 在点击时播放指定的声音                       |
| [autoclick](#autoclick)  | 即使没有点击，也要继续进行                   |
| [click](#click)      | 在不显示单击等待光标的情况下输入单击等待状态 |
### 光标

| 命令         | 描述                                         |
|--------------|----------------------------------------------|
| [setcursor](#setcursor)    | 指定单击等待光标的图形文件                   |
| [abssetcursor](#abssetcursor) | 锁定鼠标位置并指定单击等待光标的图形文件     |
| [mousecursor](#mousecursor)  | 为通用鼠标光标指定图形文件（目前不建议使用） |
### 图片显示

| 命令       | 描述                                                 |
|------------|------------------------------------------------------|
| [transmode](#transmode)  | 更改alpha混合透明度模式                              |
| [underline](#underline)  | 设定立绘底线                                         |
| [bgalia](#bgalia)     | 为非标准背景设置参数                                 |
| [humanz](#humanz)     | 为精灵和立绘指定重叠优先级                           |
| [windowback](#windowback) | 在与立绘相同的位置插入文本窗口                       |
| [bg](#bg)         | 设置背景图像                                         |
| [ld](#ld)         | 设置立绘                                             |
| [cl](#cl)         | 抹掉指定的立绘                                       |
| [tal](#tal)        | 修改立绘透明度                                       |
| [print](#print)      | 显示所有图像，删除那些不应该存在的图像               |
| [lsp](#lsp)        | 将精灵加载到内存中，下次刷新时显示                   |
| [lsph](#lsph)       | 将精灵加载到内存中，默认不显示，覆盖最后一个无效精灵 |
| [csp](#csp)        | 从内存中删除精灵                                     |
| [vsp](#vsp)        | 切换精灵显示（必须首先通过lsp/lsph加载）             |
| [spstr](#spstr)      | 通过重写文本精灵来更改复杂按钮上的文本字符串         |
| [msp](#msp)        | 更改精灵位置（方法1）                                |
| [amsp](#amsp)       | 更改精灵位置（方法2）                                |
| [cell](#cell)       | 手动指定精灵的单元格                                 |
| [blt](#blt)        | 瞬间将图像放大到屏幕上                               |
| [ofscpy](#ofscpy)     | 将 blt 绘制的图像传输到屏幕外缓冲区                  |
| [repaint](#repaint)    | redraw screen                                        |
### 图片特效

| 命令        | 描述                         |
|-------------|------------------------------|
| [effect](#effect)      | 指定特效                     |
| [effectblank](#effectblank) | 特效结束后指定等待时间       |
| [effectcut](#effectcut)   | 在选择对话框中切换特效运行时 |
| [quake](#quake)       | 在屏幕上造成晃动特效         |
| [quakex](#quakex)      | 在屏幕上产生水平晃动特效     |
| [quakey](#quakey)      | 在屏幕上造成垂直晃动特效     |
| [monocro](#monocro)     | 使屏幕呈单色                 |
| [nega](#nega)        | 使屏幕呈阴性                 |
### 字符/数字/显示栏

| 命令       | 描述               |
|------------|--------------------|
| [%](#%)          | 显示数字变量的内容 |
| [\$](#\$)          | 显示字符变量的内容 |
| [bar](#bar)        | 创建和显示显示栏   |
| [barclear](#barclear)   | 清除显示栏         |
| [prnum](#prnum)      | 初始化数字标签     |
| [prnumclear](#prnumclear) | 清除数字标签       |
### 音乐/SFX播放

| 命令          | 描述                                                        |
|---------------|-------------------------------------------------------------|
| [cdfadeout](#cdfadeout)     | 指定CD-DA淡出时间                                           |
| [mp3fadeout](#mp3fadeout)    | 指定mp3淡出时间                                             |
| [play](#play)          | 播放CD-DA或MIDI                                             |
| [playonce](#playonce)      | 只播放一次指定的CD-DA轨道或MIDI文件                         |
| [playstop](#playstop)      | 停止 CD-DA 或 MIDI 播放                                     |
| [wave](#wave)          | 只播放一次WAV文件                                           |
| [waveloop](#waveloop)      | 循环播放WAV文件                                             |
| [wavestop](#wavestop)      | 停止WAV文件播放                                             |
| [mp3](#mp3)           | 只播放一次指定的mp3文件                                     |
| [mp3loop](#mp3loop)       | 循环播放mp3文件                                             |
| [mp3save](#mp3save)       | 如果游戏保存时处于mp3播放中，当加载游戏时，请在该点恢复播放 |
| [dsound](#dsound)        | 声明您正在使用DirectSound（最新版本中不需要）               |
| [dwave](#dwave)         | 仅使用DirectSound播放一次WAV文件                            |
| [dwaveloop](#dwaveloop)     | 使用DirectSound循环播放WAV文件                              |
| [dwavestop](#dwavestop)     | 在DirectSound中停止WAV文件播放                              |
| [dwaveload](#dwaveload)     | 将WAV文件加载到内存                                         |
| [dwaveplay](#dwaveplay)     | 播放一次已经在内存中的WAV文件                               |
| [dwaveplayloop](#dwaveplayloop) | 循环播放已经在内存中的WAV文件                               |
| [stop](#stop)          | 停止播放所有音乐                                            |
### 影片播放

| 命令     | 描述         |
|----------|--------------|
| [avi](#avi)      | 播放AVI文件  |
| [mpegplay](#mpegplay) | 播放MPEG文件 |
### 选项

| 命令        | 描述                                           |
|-------------|------------------------------------------------|
| [selectcolor](#selectcolor) | 指定选项文本颜色                               |
| [selectvoice](#selectvoice) | 指定声音在选项时播放                           | 
| [select](#select)      | 设置一个选项                                   |
| [selgosub](#selgosub)    | 设置一个跳转到子语句块的选项                   |
| [selnum](#selnum)      | 显示所选选项，并将其结果添加到指定的数值变量中 |
### 跳转

| 命令   | 描述                      |
|--------|---------------------------|
| [goto](#goto)   | 跳转到指定的标签          |
| [skip](#skip)   | 跳过后续x行脚本           |
| [gosub](#gosub)  | 调用子语句块              |
| [return](#return) | 从子语句块返回            |
| [jumpf](#jumpf)  | 跳转到下一个~符号的位置   |
| [jumpb](#jumpb)  | 跳转到最后一个~符号的位置 |
### 点击时跳转到标志

| 命令     | 描述                                               |
|----------|----------------------------------------------------|
| [trap](#trap)     | 左键单击跳转到指定的标签                           |
| [lr_trap](#lr_trap)  | 左键或右键单击跳转到指定的标签                     |
| [trap2](#trap2)    | 当设置“快进到下一个选择”时，左键单击指定标签       |
| [lr_trap2](#lr_trap2) | 当设置“快进到下一个选项”时，左键或右键单击指定标签 |
### 图片按钮

| 命令        | 描述                                                  |
|-------------|-------------------------------------------------------|
| [btndef](#btndef)      | 将按钮图形文件加载到内存中。                          |
| [btn](#btn)         | 将图像初始化为按钮（方法1）                           |
| [btnwait](#btnwait)     | 显示图像按钮并将其置于单击等待状态（方法1）           |
| [btnwait2](#btnwait2)    | 显示图像按钮并将其置于单击等待状态（方法2）           |
| [spbtn](#spbtn)       | 将精灵指定为图像按钮                                  |
| [getbtntimer](#getbtntimer) | 获取自我们进入btnwait到数字变量以来已经过去了多少时间 |
| [btntime](#btntime)     | 为图像按钮功能创建时间限制                            |
| [exbtn](#exbtn)       | 创建一个复杂（复合）按钮                              |
| [exbtn_d](#exbtn_d)     | 在使用复杂按钮时指定光标行为                          |
### 等待/计时器

| 命令       | 描述                             |
|------------|----------------------------------|
| [!d](#!)         | 等待指定时间                     |
| [!w](#!)         | 等待指定时间，忽略点击           |
| [delay](#delay)      | 造成时间延迟（方法1）            |
| [wait](#wait)       | 造成时间延迟（方法2）            |
| [resettimer](#resettimer) | 重置内部计时器                   |
| [waittimer](#waittimer)  | 等待指定时间（按内部计时器计算） |
| [gettimer](#gettimer)   | 获取内部计时器的值               |
| [spwait](#spwait)     | 等到指定的精灵号码的动画结束     |
### 可变操作/计算

| 命令       | 描述                                                |
|------------|-----------------------------------------------------|
| [stralias](#stralias)   | 创建字符串别名/文件名别名                           |
| [numalias](#numalias)   | 创建一个数字变量别名                                |
| [intlimit](#intlimit)   | 为数字变量设置最大值和最小值                        |
| [dim](#dim)        | 声明数组变量                                        |
| [mov](#mov)        | 将值加载到数字或字符变量中                          |
| [mov3～mov10](#mov3～mov10) | 将值加载到多个数字或字符变量中                     |
| [movl](#movl)       | 将整行加载到数组中                                  |
| [add](#add)        | 加上数字                                            |
| [sub](#sub)        | 减去数字                                            |
| [inc](#inc)        | 加上变量                                            |
| [dec](#dec)        | 减去变量                                            |
| [mul](#mul)        | 乘上数字                                            |
| [div](#div)        | 除以数字                                            |
| [mod](#mod)        | mod（请注意，这是一个程序化模组，而不是真正的模组） |
| [rnd](#rnd)        | 创建一个随机数（方法1）                             |
| [rnd2](#rnd2)       | 创建一个随机数（方法2）                             |
| [itoa](#itoa)       | 将数字变量更改为字符或字符串                        |
| [atoi](#atoi)       | 将字符变量更改为数字                                |
### 条件表达式/循环

| 命令     | 描述                         |
|----------|------------------------------|
| [if](#if)       | if(条件) { commands }        |
| [notif](#notif)    | if (!(条件)) { commands }    |
| [cmp](#cmp)      | 比较字符变量                 |
| [fchk](#fchk)     | 检查指定的图像标签是否已读取 |
| [lchk](#lchk)     | 检查指定的标签是否已读取     |
| [for](#for) | 循环命令                    |
| [break](#break)    | 中断for循环                  |
### 右键功能

| 命令            | 描述                         |
|-----------------|------------------------------|
| [rmenu](#rmenu)           | 右键单击时初始化并显示菜单   |
| [menusetwindow](#menusetwindow)   | 右键单击菜单的初始化窗口     |
| [savename](#savename)        | 为右键单击菜单指定保存文件名 |
| [menuselectcolor](#menuselectcolor) | 为右键单击菜单文本指定颜色   |
| [menuselectvoice](#menuselectvoice) | 为右键单击菜单指定系统声音   |
| [rlookback](#rlookback)       | 右键单击即可跳转到日志模式   |
| [roff](#roff)            | 忽略右键单击                 |
| [rmode](#rmode)           | 打开和关闭右键单击的可用性   |
### 日志模式

| 命令           | 描述                         |
|----------------|------------------------------|
| [lookbackbutton](#lookbackbutton) | 指定进入日志模式的图像按钮   |
| [lookbackcolor](#lookbackcolor)  | 为日志模式指定文本颜色       |
| [lookbackvoice](#lookbackvoice)  | 在日志模式下上下翻页播放声音 |
| [lookbackflush](#lookbackflush)  | 清除日志模式                 |
### 快进模式

| 命令           | 描述                                           |
|----------------|------------------------------------------------|
| [kidokuskip](#kidokuskip)     | 打开快进模式                                   |
| [mode_wave_demo](#mode_wave_demo) | 即使指定了“快进到下一个选项”，也要播放WAVE文件 |
| [skipoff](#skipoff)        | 关闭快进模式                                   |
### 文件访问日志/全局变量

| 命令     | 描述                      |
|----------|---------------------------|
| [filelog](#filelog)  | 尝试创建/使用文件访问日志 |
| [globalon](#globalon) | 允许使用全局变量          |
| [labellog](#labellog) | 访问标签日志              |
### 存档/读档

| 命令          | 描述                       |
|---------------|----------------------------|
| [savenumber](#savenumber)    | 修改存档数量限制           |
| [savegame](#savegame)      | 在指定的存档文件中保存游戏 |
| [loadgame](#loadgame)      | 从指定的存档文件中加载游戏 |
| [savefileexist](#savefileexist) | 检查存档文件是否存在       |
| [saveon](#saveon)        | 进入保存对话框             |
| [saveoff](#saveoff)       | 退出保存对话框             |
### 其他功能

| 命令       | 描述                         |
|------------|------------------------------|
| [mesbox](#mesbox)     | 创建一个消息框               |
| [inputstr](#inputstr)   | 等待玩家输入字符（方法1）    |
| [input](#input)      | 等待玩家输入字符（方法2）    |
| [clickpos](#clickpos)   | 获取光标单击坐标             |
| [systemcall](#systemcall) | 执行右键单击菜单中列出的操作 |
### 模式自定义功能

| 命令          | 描述                                                         |
|---------------|--------------------------------------------------------------|
| [automode](#automode)      | 允许使用自动模式                                             |
| [automode_time](#automode_time) | 当没有播放声音时，指定自动模式下的字符延迟时间               |
| [defvoicevol](#defvoicevol)   | 为语音设置默认音量（新命令）                                 |
| [defsevol](#defsevol)      | 为 SFX 设置默认音量                                          |
| [defmp3vol](#defmp3vol)     | 为mp3文件设置默认音量                                        |
| [mode_saya](#mode_saya)     | 允许使用同人游戏"Saya ~Labyrinth of Immorality~"中看到的模式 |
| [mode_ext](#mode_ext)      | 允许使用“Gin‘iro”使用的自动模式                              |
| [mode800](#mode800)       | 设置屏幕大小为800x600                                        |
### 插件/归档

| 命令            | 描述                                                            |
|-----------------|-----------------------------------------------------------------|
| [soundpressplgin](#soundpressplgin) | 通过插件/dll加载压缩音频功能（现在只需使用DirectSound命令即可） |
| [spi](#spi)             | 通过插件/dll加载压缩图像功能                                    |
| [arc](#arc)             | 使用指定的归档                                                  |
| [nsa](#nsa)             | 打开NSA存档访问权限                                             |
| [nsadir](#nsadir)          | 指定NSA档案所在的文件夹                                         |
### 命令

| 命令       | 描述           |
|------------|----------------|
| [versionstr](#versionstr) | 修改版本字符串 |
| [caption](#caption)    | 修改窗口标题   |
### 数据解析

| 命令       | 描述                              |
|------------|-----------------------------------|
| [date](#date)       | 获取年份、月份和日期              |
| [time](#time)       | 获取当前时间按小时、分钟和秒      |
| [savetime](#savetime)   | 获取指定保存文件的保存日期        |
| [getversion](#getversion) | 获取当前NScripter版本的版本字符串 |
| [getreg](#getreg)     | 从Windows注册表中获取值           |
| [getini](#getini)     | 读取一个ini文件                   |
### 菜单栏功能

| 命令            | 描述                                 |
|-----------------|--------------------------------------|
| [killmenu](#killmenu)        | 擦除菜单栏                           |
| [defaultspeed](#defaultspeed)    | 在菜单栏上指定文本显示速度为可选择   |
| [!sd](#!sd)             | 使用默认速度命令传下来的文本显示速度 |
| [menu_full](#menu_full)       | 进入全屏模式                         |
| [menu_window](#menu_window)     | 进入窗口模式                         |
| [menu_click_def](#menu_click_def)  | 进入默认菜单栏操作模式               |
| [menu_click_page](#menu_click_page) | 进入菜单显示每个页面的模式           |
### 系统自定义功能

| 命令          | 描述                                                 |
|---------------|------------------------------------------------------|
| *customsel    | 与csel命令交互的标签                                 |
| textgosub     | 通常用于在系统自定义中的单击等待状态期间提供弹出文本 |
| csel          | 在系统自定义中划分选择                               |
| cselbtn       | 创建带有选择文本的按钮                               |
| getcselnum    | 获取csel选择分支的数字                               |
| cselgoto      | 跳转到csel创建的标签                                 |
| textbtnwait   | 进入自定义等待定义的单击等待状态                     |
| selectbtnwait | 进入自定义的点击等待状态                             |
| texec         | delete text while waiting for repagination           |
| getcursorpos  | 获取文本光标的当前位置                               |

## 函数手册
### \*define
```
*define
```
表示定义块开始的特殊标签。

### \*start
```
*start
```
此标签表示程序块本身的开始。

### game
```
game
```
结束定义块并开始游戏。

### reset
```
reset
```
重置游戏并返回到开头。

### definereset
```
definereset
```
这是一个特殊的重置命令，从*define开始强制重新解释脚本。

### end
```
end
```
结束程序并关闭窗口。

### *
```
*标签名称
```
创建该名称的标签。 您可以使用goto等语句跳转到此标签。

名称可以由数字（但不能在第一个位置）、1字节字符和下划线组成，但仅此而已。
```
允许 ）　　  *HAJIMARI
　　　　　　　*Mike_Tom
　　　　　　　　　*day01

不允许 ）    *始まり　　　（使用2字节字符）
　　　　　　　*Mike&Tom　（使用特殊符号)
　　　　　　　*01day　　　（第一个位置数字）
```

### ;
```
;注释文本
```
以下所有文本；被视为注释文本，因此被解释器忽略。

### :
```
<command>:<command>
```
您可以使用冒号代替回车，以分离不同的命令。 您最常看到if语句中使用的冒号,即
```
if %0=1 command1:command2:command3 ...
```

### %
```
%<数字变量>
```
数字变量范围从%0～%999到1000。

0-199是一般变量，200-999是全局变量。

一般变量在游戏重新启动、重置或许多其他事情时重新初始化，但全局变量保留其值。

换句话说，一般变量在保存时间和加载时间保存和加载时间，但全局变量始终保持不变。

因此，在做数学时最好使用通用变量，并将全局变量用于清晰的标志等。

如果您希望使用全局变量，则必须在定义块的某个位置指定命令globalon。

数字变量的默认值为0。

### $
```
$<字符变量>
```
这些作用与数字变量完全相同——包括1000变量限制和一般与全局名称，但用于字符。 

字符变量的默认值为""。

### ?
```
?<number>
```
由dim命令声明的数组变量。

这些变量的范围从?0到?199，总共200。

这些可能不会用作全局变量。

### ~
```
~
```
jumpf和jumpb目标的标签。

请不要在jumpf/jumpb命令和~之间放置任何显示文本。

### `
```
`<1字节字符>
```
反引号（`）是onscripter-20050602及更高版本的保留标志，允许使用1字节字符。 它应该放在使用1字节字符的每个脚本行的开头，也放在菜单和其他命令中1字节字符字符串的开头。
```
示例1：文本显示
Original Japanese:
アパートに着いたときには、もう全身ずぶ濡れだった。@
バイト帰りに道を歩いていたら、いきなり雨が降ってきやがったのだ。@
「ちくしょー…」@
ぶつぶつ言いながらオレは鍵を開け、我が家へと入る。@

English:
` I was already soaked from head to toe by the time I got to my apartment.@
` I mean, there I was, walking home from work, and then it started raining like hell.@
`"Goddamn it--!"@
` I grumbled as I turned the key in the lock, opened the door to my apartment, and walked in.@

示例2：右键单击菜单
Original Japanese:
rmenu "セーブ",save,"ロード",load,"回想モード",lookback,"ウインドウ消去",windowerase,"最初から",reset

English:
rmenu "`Save",save,"`Load",load,"`Log Mode",lookback,"`Hide Text",windowerase,"`Back to Title Menu",reset

示例3：字符串变量
Original Japanese:
mov $chapter,"６６６．ようこそ、ハードゲイラーＭＥＮへ！"

English:
mov $chapter,"`666. Welcome to Haado Gei RaMEN (and abandon all hope ye who enter?)!"

示例4：LSP即时字符串显示
Original Japanese:
lsp 0,":s#BEDEAD死ね！"

English:
lsp 0,":s#BEDEAD`Now Die!"
```

### /
```
/
```
如果您在此斜杠后直接写换行符，那么它将被忽略。

### setwindow
```
setwindow <number>,<number>…（11 total numbers, including the 2 to the left and the 1 to the right）…<number>,#rrggbb,<number>,<number>,<number>,<number>

-or-

setwindow <number>,<number>…（11 total numbers, including the 2 to the left and the 1 to the right）…<number>,<character string>,<number>,<number>
```
设置文本窗口。

当文本窗口的背景是使用alpha图层纯色时，使用第一种形式。

当文本窗口的背景是图形文件时，使用第二种形式。

前11个数字如下，从左到右：

文本左上角的x坐标，文本左上角的y坐标，文本列，文本行，文本字体大小x，文本字体大小y，间距x，间距y，默认文本速度，粗体字开关（0-否；1-是），下拉阴影切换（0-否；1-是）。

对于第一种形式，其余变量是：窗口颜色、窗口左上角x、窗口左上角y、窗口右下角x、窗口右下角y。

对于第二种形式，其余变量是：图形文件名、窗口左上角x、窗口左上角y、窗口右下角x、窗口右下角y。

默认情况下，文本窗口占据全屏，有点半透明，字体为26x26像素，间距为0.1，左上角坐标为8,16，有23列2字节列和16行，启用粗体和下拉阴影，速度为20，半透明颜色为#999999。

要手动声明默认值，您需要执行以下操作：
setwindow 8,16,20,23,26,26,0,2,20,1,1,#999999,0,0,639,479 

### setwindow2
```
setwindow2 "window cg file name"
-or-
setwindow2 #rrggbb
setwindow2 ":c;twindow2.bmp"
```
这修改了文本窗口的外观，而无需删除它或文本日志。

此命令只能修改setwindow中首次指定的图像文件或颜色，并且不能修改其他参数。

### textoff
```
textoff
```
隐藏文本窗口。

### texton
```
texton
```
取消隐藏/显示文本窗口。

### windoweffect
```
windoweffect <number>(,<number>(,<character string>))
```
设置文本窗口隐藏或取消隐藏时的特效。 这些参数与特效相同，不包括这里没有特效编号参数的事实。例如：
```
　　　　windoweffect 10,1000 
```
　　
### erasetextwindow
```
erasetextwindow <{0,1}>
```
如果为0，则文本窗口在特效运行时保持不变。

如果1（这是默认值），文本窗口将在特效运行时隐藏。

### defaultfont
```
defaultfont <character string>
```
定义默认字体。

如果不使用此命令，NScripter默认为MS Gothic。

ONScripter默认为default.ttf。

### !s
```
!s<number>
```
更改文本显示速度（以毫秒为单位）。

这个数字\*必须\*是一个常量，而不是一个变量。 如果您想使用变量，请使用textspeed命令。

### \#
```
#rrggbb
```
更改文本的颜色-使用HTML十六进制颜色代码。 请注意，这只会更改下一个文本显示，而不是之前或之后的任何文本显示，所以要小心。

### textclear
```
textclear
```
仅抹掉文本窗口的内容。

### locate
```
locate <number>,<number>
```
更改文本插入的位置。 这些值以文本指标为单位，而不是以像素为单位。

### puttext
```
puttext <character string>
```
指示屏幕上指定的字符串。 此命令最常在if语句中用于显示一些短指示器，但除此之外，其功效有限。

使用puttext时，您不得使用任何变量指定/值函数（例如%或$）。

### br
```
br
```
在文本窗口中插入换行符。

当您想要空白行或类似的东西时，请使用这个。

### textspeed
```
textspeed <number>
```
更改文本显示速度。

这是!s与相同的功能，除此之外你可以在这里指定一个变量。

### @
```
@
```
进入入单击等待状态。

### \
```
\
```
进入页末等待状态，同一行上此符号后面的任何新字符都会被忽略。 一旦玩家点击，他将被发送到下一页。

### clickstr
```
clickstr <character string>,<numerical variable>
```
当解释器遇到指定字符串中的字符时，此函数强制单击等待状态。

但是，如果恰好在该字符后面有一个单击等待命令，或者该字符的前置有一个1字节下划线（_），则不会发生这种强制单击等待状态。

第二个参数决定了这是一个简单的等待状态，还是文本页面是翻页的。 如果强制单击等待字符串恰好短于（最大行长数），则会发生翻页。

这是一个为了您的方便的功能，但要小心——如果您不小心，您很容易导致下一行溢出。

在这种情况下，请决定是允许默认换行符，还是在适当的地方手动插入换行符。

字符串必须是2字节字符。

例如：
```
click "」。！？",2
```
　
### _
```
_
```
如果您在此下划线后直接写换行符，则换行符将被忽略。

### linepage
```
linepage
```
设置这意味着即使您没有指定带有\的页面提要，自动翻页也会在行尾发生。

这意味着您永远不必手动指定行或页面翻页。

但是，如果您决定将@、\或clickstr与此命令一起使用，请小心将它们保持在一致的状态。

### clickvoice
```
clickvoice <character string>,<character string>
```
第一个字符串是在单击等待状态下单击按钮时播放的WAV文件的名称。 第二个字符串确定这是默认的单击等待状态，还是表单翻页的单击等待状态。

### autoclick
```
autoclick <number>
```
如果单击等待状态已超过指定时间（以毫秒为单位），请像自动单击鼠标一样继续。 此命令在引擎过场动画中特别有用。

如果指定的数字为0，则此命令将无法激活。

### click
```
click
```
等待点击。

### setcursor
```
setcursor <character string>(<character string>),<number>,<number>
```
加载并显示光标定义文件，以便在单击等待状态期间使用。

字符串从左到右是正常等待状态的光标和页面翻页等待状态的光标。

这些数字包括一个（x，y）坐标，相对于首选文本的左上角像素。

默认情况下，这些变量是：
```
":l/3,160,2;cursor0.bmp"(":l/3,160,2;cursor1.bmp"),0,0です。 
```

### abssetcursor
```
abssetcursor <cursor string>,<character string>,<number>,<number>
```
与setcursor的功能相同，但使用绝对屏幕坐标，而不是相对坐标。

### mousecursor
```
mousecursor <character string>
```
加载Windows鼠标光标定义文件（.cur）并使用它。

### transmode
```
transmode {leftup,copy,alpha}
```
更改默认透明度模式。leftup是默认值。

alpha模式下，如果没有alpha通道，会用图片右半作为alpha通道。

### underline
```
underline <number>
```
指定立绘的底线。 默认情况下是479.

### bgalia
```
bgalia <x>,<y>,<width>,<height>
```
当您希望创建具有特殊维度或位置的背景时，应使用此命令。

在绝对屏幕位置（x，y）创建尺寸（宽度、高度）的背景窗格。
### humanz
```
humanz <number>
```
当精灵和图片重叠时指定图像优先级（z轴）。

通过使用此命令，您可以直接在精灵上绘制图片。

默认值为25。

### windowback
```
windowback
```
将文本窗口插入与立绘相同的位置。 可用于“位置字幕”特效。

### bg
```
bg <character string>,<effect>
-OR-
bg #rrggbb,<effect>
-OR-
bg {black,white},<effect>
```
载入背景图像。 第一个案例来自文件，第二个案例是单色填充，最后一个案例是黑色或白色填充。

### ld
```
ld {l,c,r},<character string>,<effect>
```
加载一张立绘。l = 左，r=右，c=中心。

字符串是图像文件名；图像标签也会自动生成。

### cl
```
cl {l,c,r,a},<effect>
```
清除当前图片元素
如果您指定“a”，那么这将清除所有内容。

### tal
```
tal {l,c,r},<number>
```
将指定立绘（左、中、右）的透明度更改为指定数字。

### print
```
print <effect>
```
利用指定特效绘制到屏幕上。

您可以以两种方式之一指定要使用的特效：
１）按特效标签
　　　　0…只绘制内存，而不是屏幕
　　　　1…立即显示
　　　　1<…由[effect](#effect)命令定义的特效的标签
```
　　　　bg "test.jpg",0
　　　　ld c,"testman.jpg",1
　　　　cl c,3
```
２）直接指定
　　　　使用与[effect](#effect)命令相同的参数直接指定特效
```
　　　　bg "test.jpg",10,1000
　　　　ld "testman.jpg",15,2000,"mask.bmp"
```

### lsp
```
lsp <sprite number>,<character string>,<number>,<number>(,<number>)
```
加载并显示精灵。 精灵序号从0到49。

其他数字是，从左到右，（左上角像素的x坐标），（左上角像素的y坐标），（精灵的透明度值-可选）。

[lsp](#lsp)和[lsph](#lsph)的唯一区别是精灵的起始状态，在[lsp](#lsp)中，精灵被显示；在[lsph](#lsph)中，精灵是隐藏的（然后可以用[vsp](#vsp)显示）。

### lsph
```
lsph <sprite number>,<character string>,<number>,<number>(,<number>)
```
请参阅lsp的文档。

### csp
```
csp <sprite number>
```
抹掉给定的精灵。

如果精灵数为-1，则擦除所有精灵。

### vsp
```
vsp <sprite number>,<number>
```
打开和关闭指定精灵的显示。0关闭，1打开。

### spstr
```
spstr <控制字符串>
```
您可以使用此精灵通过使用[exbtn](#exbtn)命令的控制字符串格式手动控制精灵。

就像[csp](#csp)、[lsp](#lsp)和[vsp](#vsp)一样，您需要在之后直接调用[print](#print)，才能在屏幕上显示任何东西。
```
spstr "C11P10,2P9"
```
　　
### msp
```
msp <sprite number>,<number>,<number>,<number>
```
移动指定序号的精灵。 从左到右的其他变量是：x、y、透明度。

与[tal](#tal)命令和其他精灵系统命令一样，[msp](msp)的结果不会显示在屏幕上（这是为了批量处理的便利性和速度）。

因此，在[msp](#msp)之后调用任何文本或图像显示命令之前，请在继续之前调用打印命令更新屏幕。

### amsp
```
amsp <sprite number>,<x>,<y>,<transparency>
```
类似于[msp](#msp)，但是使用绝对位置，而不是增量。

例如：
```
amsp 2,5,2,100
```
这选中精灵2，将其移动到5,2（绝对位置），并赋予其100%的透明度。
　
### cell
```
cell <sprite number>,<cell number>
```
手动指定精灵的单元格。 由于这只是内部状态的变化，因此您有责任随后使用[print](#print)命令或其他此类方法将其反映在屏幕上。

### blt
```
blt <onscreen x>,<onscreen y>,<onscreen height>,<onscreen width>,<button image x>,<button image y>,<button image width>,<button image height>
```
如果您想立即在屏幕上拆分图像，请使用此命令（例如，AIR的opening engine-driven过场动画）。

这使用按钮图像缓冲区，因此请事先使用[btndef](#btndef)填充所述缓冲区。

如果图像按钮的宽度大于屏幕宽度，则图像会相应缩放。

（例如，如果一次加载4张半大小的图像，然后使用blt，那么它们会立即被一个接一个地显示，没有后图像效果，就像高速动画一样。 这种效果在AIR中使用。）

此命令直接写入屏幕，而不是写入后缓冲区。 因此，在Blitting结束后，屏幕的内容可能不确定，在这种情况下，您应该使用[yscpy](#yscpy)（保存旧状态）后跟[bg](#bg)（加载新状态）。

Even if one saves in the midst of this blitting, the images will not be screenshotted for the save caption.
Therefore, please limit your usage of this technique (for instance, a demo, or a status screen/save/load menu in an SLG).

### ofscpy
将使用[blt](#blt)命令绘制的内容复制到屏幕外缓冲区。

说明：

一旦您将图像放到屏幕上，现在您想对它调用特效，您将使用此命令将其复制到屏幕外缓冲区。

使用此命令创建的屏幕外缓冲区可以用于特效，就像任何其他屏幕缓冲区一样。

图像和特效将显示，但它们不会通过/保存被记住。

通过同时使用[blt](#blt)和[yscpy](#yscpy)，您可以创建引擎过场动画等（如AIR中发现的场景），事实上，这就是创建这些命令的原因。 因此，它们可能很难使用，但请耐心等待。

用法：
```
btndef "～"
;读取动画图片

bg ～
ld c,～
;在此之前，所有命令都是标准图像命令，因此它们会显示良好状态。

resettimer
blt ～
waittimer 100
blt ～
waittimer 100
;以这种方式，我们可以在引擎过场动画中一个接一个地显示图像。

;现在我们已经划分了一堆图片，我们想用特效等处理图像，我们需要将最终产品复制到屏幕外缓冲区。
ofscpy
bg ～

;现在，你可以做任何你想做的事情，无论是屏幕还是屏幕外缓冲区。
bg ～
ld c,～
```

### repaint
重新绘制屏幕。 如果您开始在屏幕上获得奇怪的伪影等，请调用此命令。

### effect
```
effect <number>,<number>(,<number>(,<character string>))
```
为内置特效分配特效编号。

分配特效编号后，您可以在图像显示命令中使用它

从左到右，变量是：特效编号、内置特效索引、特效运行时（以毫秒为单位）、模式图像文件名。

但是，如果您使用的是内置特效，您可能会省略最后两个变量。

由于特效编号0中插槽的特效将立即显示下一个图像显示命令，请在1点开始特效。

或者，如果您要使用0，请记得尽快调用图像显示命令。

默认情况下，内置特效索引1根本不是特效，而是将特效运行时间设置为0——即时显示。

内置特效索引
即时显示。 不需要运行时变量。

左侧百叶窗

右侧百叶窗

向上百叶窗

向下百叶窗

左侧帷幕

右侧帷幕

向上的帷幕

向下帷幕

像素交叉渐变

左侧滚动

右侧滚动

向上滚动

向下滚动

通过遮罩图片褪色。 您必须为此设置文件名，指向遮罩bmp（256种颜色或全彩色）。 在这个遮罩bmp中，白色区域缓慢褪色，黑色区域迅速褪色。

马赛克淡出。 调用此效果后，屏幕状态将与您使用效果数字0一样不确定，因此请在之后立即调用显示命令，如[print](#print)。

通过遮罩马赛克淡入淡出。 这与15类似，只是处理器密集得多，所以要小心使用这种效果。

```
　　　　effect 1,1
　　　　effect 2,4,1000
　　　　effect 3,15,2000,"m3.bmp"
```

### effectblank
```
effectblank <number>
```
这是简单设置（以毫秒为单位）解释器在效果结束后应该等待多长时间才能解释下一个命令。

如果效果碰巧是内置效果索引1，那么此命令没有效果，因此没有延迟。

### effectcut
```
effectcut
```
在“快进直到下一个选择”模式下跳过所有效果。

### quake
```
quake <amplitude>,<time in millseconds>
```
　在屏幕上引起所述振幅和所述时间的随机震动效果。 在旧显卡上可能很慢。
　
### quakex
```
quakex <amplitude>,<time in millseconds>
```
就像quake一样，只是它只是从一边到另一边（横向）摇晃屏幕。

### quakey
```
quakey <amplitude>,<time in millseconds>
```
就像quake一样，只是它只是上下摇晃屏幕（垂直）。

### monocro
```
monocro #rrggbb -or- monocro off
```
使用指定的颜色作为底座，将屏幕褪色为单色。

文本窗口和鼠标光标不会效仿。

如果您使用“off”作为参数，则颜色将恢复正常。

### nega
```
nega <number>
```
If 1 or 2, causes a negative of the current image -- one of which is monochrome, one of which is not.
If 0, flips the image back to positive.
Neither monocro or nega do any screen drawing in and of themselves, so please call print directly afterwards.

### %
```
%<number>
```
数字变量标签。 使用这个来访问它们的内容。

### $
```
$<number>
```
字符变量的标签。 使用这个来访问它们的内容。

### bar
```
bar <bar #>,<bar curr. value>,<x>,<y>,<width>,<height>,<bar max value>,<color>
```
初始化并显示条形图。宽度和高度变量表示当条在最大值时会有多大。当然，当它不处于最大值时，条形图会按比例缩小。条形图是左对齐的。由于条只是以指定颜色从左到右填充，请确保未填充区域的背景颜色在背景本身中绘制。最后，如果您不调用[print](#print)命令（或类似内容），那么栏（或条的当前状态）当然不会显示在屏幕上。

### barclear

清除条。

You can think of bars as being like life bars in fighting games. Kind of.

### prnum
```
prnum <numerical value label number>,<current value>,x,y,<character width>,<character height>,<color>
```
创建一个数值标签，然后在给定的大小和颜色下在给定位置进行划分当前值。

它的值范围为3列，因此从0-999。

您需要调用打印命令或类似的东西才能在屏幕上实际显示此命令。

bar and prnum were specifically created for mode_saya, which was inturn specifically created for the doujin game 「Saya ～Labyrinth of Immorality～」.
目前有计划用更通用和更强大的命令来取代这一系列命令。

### prnumclear
清除给定的数字值标签。
　
### cdfadeout
```
cdfadeout <number>
```
指定以毫秒为单位从当前播放的CD-DA音频中淡出。

### mp3fadeout
```
mp3fadeout <number>
```
将mp3淡出时间设置为毫秒。
　
### play
```
play <character string>
```
播放 MIDI 文件或 CD 音频。

如果您指定文件名，则将播放相应的MIDI文件，但如果您指定序号，则将播放适当的CD轨道。

play将循环MIDI文件/CD音频；如果您希望文件/轨道播放一次，请使用[playonce](#playonce)命令。

### playonce
```
playonce <character string>
```
有关更多信息，请参阅[play](#play)文档。

### playstop
```
playstop
```
停止播放 MIDI/CD 音频。

### wave
```
wave <character string>
```
播放指定的WAV文件。

wave只播放一次，但[waveloop](#waveloop)会循环它。

### waveloop
```
waveloop <character string>
```
请参阅[wave](#wave)的文档。

### wavestop
```
wavestop
```
停止播放所有WAV文件。

### mp3
```
mp3 <character string>
```
如果正在使用mp3dec.dll（此功能已经在inscripter中集成了“免费”），您可以使用它来播放mp3文件。mp3仅播放一次，[mp3loop](#mp3loop)循环播放。 您可以在mp3播放时发出[wave](#wave)命令，不会产生不良影响。

### mp3loop
```
mp3loop <character string>
```
请参阅[mp3](#mp3)命令的文档。

### mp3save
就像[mp3](#mp3)命令一样，这只能播放一次mp3，但如果玩家在其中保存/加载，mp3将从加载时最后一个已知位置播放。
　
### dsound
您在定义块中使用它来打开DirectSound。 您需要DirectX 2+才能使用此命令。 在最新版本的NScripter中，不再需要设置此命令。

### dwave
```
dwave <number>,<filename>
```
使用DirectSound播放WAV文件，使用指定的数字作为通道号（从0-49开始）。 不同的WAV文件将在遇到时自动混合。 如果您希望在自动模式下连续播放所有声音（文本等待语音），请将所有声音设置为0频道。 只能使用此命令播放PCM文件。 此命令的使用方式与[wave](#wave)命令相同，具有混音的额外优势——因此，如果您将[mp3](#mp3)作为背景音乐播放，则需要将[dwave](#dwave)用于声音和音效。
```
dwave 0，"test.wav"
```

### dwaveloop
```
dwaveloop <number>,<filename>
```
与[dwave](#dwave)相同，但在这种情况下，它会循环WAV文件。

### dwavestop
```
dwavestop <number>
```
静音特定的通道。

### dwaveload
```
dwaveload <number>,<filename>
```
将WAV文件加载到内存中，以便与[dwaveplay](#dwaveplay)和[dwaveplayloop](#dwaveplayloop)命令一起使用。
```
dwaveload 0,"test.wav"
dwaveplay 0 dwaveplayloop 0
```

### dwaveplay
```
dwaveplay <number>
```

播放由[dwaveload](#dwaveload)加载的WAV文件。

### dwaveplayloop
```
dwaveplayloop <number>
```
循环由[dwaveload](#dwaveload)加载的WAV文件。

### stop
```
stop
```
停止播放所有声音。

### avi
```
avi <character string>,<number>
```
播放指定的AVI文件。 如果数字是1，那么如果玩家在播放电影的中间点击，电影将被跳过，玩家可以继续。如果数字为0，则玩家将被迫观看整部电影。

### mpegplay
```
mpegplay <filename>,<skip on click>
```
播放MPEG视频文件。 第二个参数可以是0或1，并确定玩家是否必须观看整部电影（0），或者是否可以通过单击跳过电影（1）。
```
mpegplay "test.mpeg",1
```

### selectcolor
```
selectcolor #rrggbb,#rrggbb
```
按顺序指定选项文本的鼠标悬停和鼠标移出颜色。

### selectvoice
```
selectvoice <character string>,<character string>,<character string>
```
指定WAV文件在选项对话框中播放。从左到右：进入选择对话框时，在选项文本的鼠标悬停时，最后在单击选项文本时。

### select
```
select <character string>,*<label to jump to>,<character string>,*<label to jump to>,…
```
显示选择，然后跳转到与所选选项关联的标签。

如果字符串设置为""，则不会显示该选项。

（这与[selnum](#selnum)和[selgosub](#selgosub)的工作方式相同）

但是，要小心，因为如果您甚至没有指定单个选项作为参数，此命令将导致解释器挂起。

### selgosub
```
selgosub <character string>,*<label to jump to>,<character string>,*<label to jump to>,…
```
工作方式与[select](#select)相同，但在这种情况下跳转到子语句块，而不是通用标签。

### selnum
```
selnum <numerical variable>,<character string>,<character string>,…
```
工作原理有点像select和selgosub，除了根据单击哪个字符串，一个数字（从0开始，然后每个字符串增加一个）加载到数字变量中，而不是发生任何类型的跳转。

### goto
```
goto *labelname
```
跳转到那个标签名称。Can cause spaghetti code. Mmmm, spaghetti ...

### skip
```
skip <number>
```
跳过指定的行数。 可以向前（-）或向后跳过（+）。

### gosub
```
gosub *labelname
```
跳转到并开始执行该标签名称。 当遇到[return](#return)命令时，直接跳回原本[gosub](#gosub)行。
### return
```
return
```
在[gosub](#gosub)调用的语句块结束时用于返回[gosub](#gosub)自身后的下一行。

### jumpf
跳转到下一个~符号。 当使用合适的标签很麻烦时，请使用这个。 然而，由于您无法真正使用这种方法进行深度嵌套控制，请不要过度使用它。
```
jumpf
;跳过此空间中的所有命令
~
;从这里开始执行
```

### jumpb

返回最后一个~符号。

### trap
```
trap *labelname -or- trap off
```
等待左键单击，然后在左键单击时跳转到指定的标签。 此陷阱模式随后立即停用，或者您可以在关闭陷阱的情况下手动停用它（在跳转发生之前）。

### lr_trap
```
lr_trap *labelname
-or-
lr_trap off
```
左右点击陷阱（或关闭所述陷阱），引导解释器指向指定的标签名称。

### trap2
```
trap2 *label name
-or- 
trap2 off
```
这与[trap](#trap)相同，除了当“跳到下一个选择”模式处于激活状态以外，应该使用[trap](#trap)。

### lr_trap2
```
lr_trap2 *labelname
-or-
lr_trap2 off
```
与[lr_trap](#lr_trap)类似，除了这个功能用于“跳到下一个选择”模式。

### btndef
```
btndef <character string>
```
设置图像按钮。 之前定义的按钮被清除。

例如，请参阅SDK的btndemo/文件夹。

### btn
```
btn <number>,<number>,<number>,<number>,<number>,<number>,<number>
```
从左到右，这是：按钮编号，x，y，宽度，高度，x3，y3。

这是您用于创建和初始化按钮的命令。 按钮编号从1开始。

生成的按钮从位置（x，y）开始，并且（宽度，高度）大小。

当鼠标光标越过按钮时，它将使用btndef位图中大小相同的矩形显示，左上角为（x3，y3）。

### btnwait
```
btnwait <numerical variable>
```
这可以作为按钮的监听器。 按钮的结果值在数值变量中返回。

返回值：

0：没有点击按钮

-1：发生了右键单击

1<=：点击按钮的次数

如果btnwait返回的值<0（没有单击按钮），那么您可以再次调用btnwait以输入相同的按钮等待状态。 但是，如果btnwait返回>=1的值（按下几次按钮），那么图像将保留在后面，但所有按钮定义都将被清除（以保存内存）。 有关示例，请参阅SDK中的btndemo/文件夹。

### btnwait2
```
btnwait2 <numerical variable>
```
这可以作为按钮的监听器。 按钮的结果值在数值变量中返回。

返回值：

0：没有点击按钮

-1：发生了右键单击

1<=：点击按钮的次数

与[btnwait](#btnwait)不同，此命令不会清除任何按钮定义。 因此，它将不断读取按钮图形文件。 现在，由于按钮即使在没有用处后仍保留在内存中，因此您应该在使用完它们后调用`btndef ""`，以释放内存。

### spbtn
```
spbtn <sprite number>,<button number>
```
就像[btn](#btn)命令一样，除了它使用精灵设置图像按钮。 未点击状态的图形进入单元格0，单击状态的图形进入单元格1。 按下按钮后，它会返回按钮编号作为值。

### getbtntimer
```
getbtntimer <variable>
```
获取当前按钮计时器的当前状态。例如，在玩家发起暂停后，您将使用此功能在适当位置重新启动按钮计时器（也许通过右键单击）。

### btntime
```
btntime <numerical variable>
```
这指定了下一个btnwait或btnwait2周期的时间限制（以毫秒为单位）。 一旦使用此命令并激活btnwait，如果在指定时间段内没有发生任何事情，那么btnwait将返回-2。

### exbtn
```
exbtn <sprite number>,<button number>,<control string>
```
这与spbtn完全相同，添加了一个尾随控制字符串。

简而言之，当玩家将鼠标悬停在exbtn控制的按钮上时，按钮不仅会移动，还可以根据控制字符串通过精灵控制对屏幕图形进行控制。

控制字符串修改如下：
```
"C<number>" 导致带有该数字的精灵被隐藏。
"P<number>" 导致带有该数字的精灵显示。
"P<number1>,<number2>" 导致精灵编号1显示在单元格2中。
```
您可以将控制字符串中三个选项中的任何数字连接起来。
```
"C10"
"C11P10"
"C11P10,2P9"
```
使用复合按钮时，需要分配鼠标光标没有触摸按钮的任何部分时会发生什么。 这需要在[exbtn_d](#exbtn_d)中设置。

按钮与任何其他图形一样，可以作为图像文件名字符字符串或精灵加载。

### exbtn_d
```
exbtn_d <control string>
```
当鼠标光标不在上面时，确定复合按钮的状态。 要查看控制字符串的格式，请参见[exbtn](#exbtn)的文档。
```
exbtn_d "P3C4C5C6P7,0"
```

### !d
```
!d<number>
```
等待指定的毫秒数，然后继续。 此状态只需单击即可取消。 该数字必须是数字常量，而不是变量，如果您想使用变量，请使用[delay](#delay)命令。

### !w
```
!w<number>
```
等待指定的毫秒数。单击即可取消。该数字必须是数字常量，而不是变量；如果您想使用变量，请使用[wait](#wait)。

### delay
```
delay <number>
```
导致指定时间的延迟（以毫秒为单位），无法通过单击取消。虽然这与关键字!d相同，但在这种情况下，您可以提供一个变量作为参数。

### wait
```
wait <number>
```
等待指定的毫秒数；单击无法取消此状态。这与关键字!w相似，但是此命令可以将变量作为参数。

### resettimer
```
resettimer
```
将内部计时器设置为0。这个计时器以毫秒的尺度运行。
### waittimer
```
waittimer <number>
```
等到内部计时器超过指定时间后再继续。 此命令是所有NScripter中最准确的计时措施。 图像效果运行时等事物的时序间隔几乎不那么准确，因此在混合和匹配计时方法时请小心。

### gettimer
```
gettimer <numerical variable>
```
获取内部计时器的当前状态。

返回一个以毫秒为单位的值，对应于自上次调用[resettimer](#resettimer)命令以来所花费的时间。
### spwait
```
spwait <sprite number>
```
等待用户剪切或上述精灵编号的动画完成。

### stralias
```
stralias <character string 1>,<character string 2>
```
将字符串1作为字符串2的别名。换句话说，在声明后，您可以在所有情况下将字符串1视为字符串2。
```
stralias man_a0 ":a/10,20,2;man_alpha.bmp"
```
现在，您可以输入”man_a0”，而不是输入”:a/10,20,2;man_alpha.bmp”。

例如，现在`
ld c,man_a0,1`等价于`ld c,”:a/10,20,2;man_alpha.bmp”,1`。

### numalias
```
numalias <character string>,<number>
```
创建一个字符串，作为数值的别名。
```
numalias ef_lshutter,2
```
所以现在，ef_lshutter相当于2，
`bg "test.bmp",ef_lshutter`相当于`bg "test.bmp",2`

　　（Really Advanced Saikyo-ryuu）
可以使用numalias为数字变量创建字符串别名。
```
numalias akari_love,0
```
现在，%akari_love 被定义为%0，`add %akari_love,10`相当于`add %0,10`。
　
### intlimit
```
intlimit <number>,<number>,<number>
```
限制数值变量的值。如果它超过设置最大值，则重置为设置最大值；如果低于设置最小值，则重置为设置最小值。按顺序，命令中的数字是：数字变量序号、最小值、最大值。
```
intlimit 0,10,20
```
这将%0限制为10到20之间。

### dim
```
dim ?0[10][20]
```
BASIC风格的数组。上面的特定数组被命名为?0，有0-10的阵列插槽，然后每个插槽都有0-20的子插槽。
```
mov ?0[2][5],20
;put 20 inside ?0[2][5]
mov %4,?0[3][1]
;%put the contents of ?0[3][1] inside %4.
？０［２］［３］＝?0[2][3]@
;displays the value of ?0[2][3].
```
通过这种方式，您可以使用数组变量，就好像它们是简单的数字变量一样。

您可以使用numalias使您的代码更易于阅读：
```
numalias enemyparam,10
dim ?enemyparam[10]
```
注意事项

请记住，数组的内容从0开始，所以在分配它们时请小心！

### mov
```
mov <variable>,<value>
```
分配一个具有新值的变量。
```
　　　　mov %3,24
　　　　mov $0,"ANONONO"
```

### mov3 ～ mov10
```
movN <numerical variable>,<number>,<number>,<number>……
```
此命令用指定的数字填充数字变量，从指定的变量开始，向上递增。

例如：
```
mov3 %3,2,4,6
is equivalent to
mov %3,2:mov %4,4:mov %5,6
```
"mov4" "mov5" "mov6" "mov7" "mov8" "mov9" "mov10"

仿照这个格式

### movl
```
movl <array variable>,<number>,<number>,……
```

一次将所以数字输入数组。
```
dim ?10[4]
dim ?20[2][3]

movl ?10,0,1,2,3,4
movl ?20[0],0,1,2,3
movl ?20[1],0,2,4,6
movl ?20[2],0,3,6,9
```

### add
```
add <numerical variable>,<number>
```
两个数字相加。如果用于字符，则会导致字符串合并。
```
　　　　add %0,6
　　　　add $5,"aaaa!"
```

### sub
```
sub <numerical variable>,<number>
```
从数字变量中减去数字。
```
　　　　sub %0,6
　　　　sub %0,%2 
```

### inc
```
inc <numerical variable>
```
将数字变量的值增加一。

### dec
```
dec <numerical variable>
```
将所述变量减小1。

### mul
```
mul <numerical variable>,<number>
```
将变量乘以数字，并将结果存储在变量中。

### div
```
div <numerical variable>,<number>
```
将变量除以数字，并截断余数。

### mod
```
mod <numerical variable>,<number>
```
在变量除以数字后返回余数（与C中的x%y命令相同）。

### rnd
```
rnd <numerical variable>,<number>
```
生成一个随机数并将其粘贴在数字变量中，从0到数字1。
```
　　　　rnd %5,100 
```
　　
### rnd2
```
rnd2 <numerical variable>,<number 1>,<number 2>
```
创建一个从数字1到数字2的随机数字。
```
　　　　rnd2 %3,10,20 
```

### itoa
```
itoa <character variable>,<number>
```
将数字转换为字符串。 类似于C中的itoa函数。
```
itoa $0,120
itoa $1,%2
```

### atoi
```
atoi <numerical variable>,<character string>
```
将字符串转换为数字变量。 工作方式与C中的相应命令相同。
```
atoi %0,"123"
atoi %3,$0
```

### if
条件语句。
```
　if <conditional statement> ({&&,&} <conditional statement>) <commands>
```
如果条件语句计算true，则执行if语句后面的命令；如果您想要命令执行的分支控件，如果条件语句为false，请使用[notif](#notif)。

这些条件可以比较数值，否则您可以使用[fchk](#fchk)。

&和&&相当于逻辑的“和”，彼此等价。
```
　　　<条件>
　　　<numerical variable> {>,<,=,>=,<=,==,!=,<>} <numerical variable>
　　　- or -
　　　fchk <character string>
```
　　　<,>，=，>=，<= 你应该已经知道了。==和=是相同的，就像!=和<>。

至于fchk，当使用名称与字符串相对应的图像时，它会返回true。
```
　　　　if %0=1 quakex 2　（basic form）
　　　　if %0=1 && %2=5 end　（multiple conditions）
　　　　if %0=2 mov %1,1:skip 2 （append additional commands with :）
　　　　notif %0=1 quakex 2　（in C, this would be if(%0!=1) quakex 2;）
```

### notif

请参阅[if](#if)的文档。

### cmp
```
cmp <numerical variable>,<character string>,<character string>
```
比较两个字符串。 如果相等，则返回0，如果右侧较大，则返回负值，如果左侧较大，则返回正值。

### fchk
```
fchk <filename>
```

检查文件日志中是否记录了图像标签。

这被用作if语句的参数。 如果图像已加载并可能在游戏中使用，则返回true。 如果没有，或者文件名不正确，则返回false。
```
ld c,":a;test.bmp",1
if fchk ":a;test.bmp" ;returns true
if fchk "test.bmp" 　;returns false
```

### lchk
```
lchk <label name>
```
与[fchk](#fchk)一样，此命令用于[if](#if)语句。 它检查是否使用/访问了特定标签（根据字符串）。
lchk *test
-而不是-
lchk "*test"
is the correct syntax.

### for
```
for %<numerical variable>=<number> to <number> (step <increment>)
:（commands in loop）
next
```
这本质上与BASIC循环相同。 For循环从第一个数字开始，然后按步进值增加（或减少），直到它超过（或低于，如果是负步进）第二个数字。 默认情况下，步进值为1。

如果您在for循环中使用[goto](#goto)或[select](#select)等方法，则会使nscripter堆栈处于不一致且易于崩溃的状态，因此请不要这样做。 今天尽自己的一份力量来根除意大利面条代码！

FOR和NEXT之间循环中的所有命令都将被执行。 如果您想过早地打破循环，请发出[break](#break)命令。 您还可以使用[gosub](#gosub)命令，在循环中不会产生不良影响。 换句话说，强烈建议将循环内的内容与循环外部的内容区分开。

### break
```
break
```
打破单个循环，在循环的下一个语句后立即进入该行。

您不能单独使用此命令完全打破嵌套循环，因此在这种情况下，您需要打破内循环，然后突破外循环。

例如：
```
;------------------------
*define
game
*start
for %0=1 to 8
for %1=6 to 2 step -2
%0，%1
if %0=4 & %1=4 break
next
next
click
end
;------------------------
```

【一种不推荐的方法】
```
break *<标签名称>
```
这种语法确实存在；它具有与[goto](#goto)语句相同的功能。

它可以使您脱离嵌套循环，但它使内循环的状态完好无损。

这导致堆栈碎片化，使以后很难调试脚本，因此请极其谨慎地使用此语法。

### rmenu
```
rmenu <character string>,<function>,…
```
在右键单击时打印右键单击菜单。

字符串是菜单项文本，该函数从下面定义的列表中选择。

系统菜单函数常量：

| 函数        | 描述                  |
|-------------|-----------------------|
| skip        | 与“跳到下一个选择”相同 |
| reset       | 重置程序              |
| save        | 转到存档菜单          |
| load        | 转到读档菜单          |
| lookback    | 转到日志模式          |
| windowerase | 最小化窗口            |
```
　　　　rmenu "SAVE",save,"LOAD",load,"LOG",lookback 
```

### menusetwindow
```
menusetwindow <number>,<number>,<number>,<number>,<number>,<number>,#rrggbb
```
创建菜单对话框窗口。

此窗口在激活时显示在屏幕上所有其他项目的上方。

从左到右，参数是：字符字体大小x，字符字体大小y，字距x，字距y，粗体（1-是；0-否），下拉阴影（1-是；0-否）；最终的#rrggbb参数是窗口颜色。

### savename
```
savename <character string 1>,<character string 2>,<character string 3>
```
指定存档文件的名称。

从左到右，字符串是：保存菜单的标题字符串，加载菜单的标题字符串，然后是保存本身的名称。

默认情况下，这些是“<セーブ>”，“<ロード>”，“しおり”——请注意，这些都是2字节的字符串。

因此，此函数仅使用2字节字符字符串作为输入。

### menuselectcolor
```
menuselectcolor
```
当启用右键单击菜单功能时，此命令设置右键单击菜单的颜色。 按顺序，颜色是鼠标悬停颜色、鼠标移出颜色和“不存在保存文件”颜色。

### menuselectvoice
```
menuselectvoice <character string>,<character string>,<character string>,<character string>,<character string>,<character string>,<character string>
```
指定为菜单选择和其他系统声音播放的WAV文件。

从左到右，字符串是：菜单打开，菜单取消，菜单项鼠标悬停，单击，禁止操作，“是”确认，“否”确认。

如果其中任何一个设置为""，则不会播放声音。

默认情况下，所有这些声音都设置为""。
### rlookback
```
rlookback
```
使用右键单击前往日志模式。
### roff
```
roff
```
将右键单击的默认行为设置为空/什么都不做。

### rmode
```
rmode <number>
```
打开（1）或关闭（0）右键单击功能。

### lookbackbutton
```
lookbackbutton <character string 1>,<character string 2>,<character string 3>,<character string 4>
```
加载按钮以用于日志模式。

从左边，字符串是：上一页按钮鼠标图形，上一页按钮鼠标关闭图形，翻页按钮鼠标按钮图形，翻页按钮鼠标关闭图形。

默认情况下，这些是“uoncur.bmp”，“uoffcur.bmp”，“doncur.bmp”，“doffcur.bmp”。

所有这些图像的大小必须相同，否则此命令将失败。

日志模式按钮无法动画。

进入日志模式的按钮位于文本窗口的右上角。

一旦设置，它的位置就无法更改，因此请确保您第一次设置正确。

### lookbackcolor
```
lookbackcolor #rrggbb
```
在日志模式下设置文本颜色。

颜色是一个十六进制值，与您在HTML中看到的相同。

### lookbackvoice
```
lookbackvoice <character string>
```
指定一个WAV文件，以便在日志模式下单击上一页/下一页按钮时播放。

### lookbackflush
```
lookbackflush
```
刷新日志模式缓冲区。

### kidokuskip

如果您使用此命令，您可以进入“跳过直到下一个选择”模式。 脚本保存在日志数据中，但无论如何，每当您遇到之前未读文本时，此模式会自动终止。

### mode_wave_demo

虽然，在“跳到下一个选择”模式下，通常不会播放WAV文件，但如果您指定此命令，那么它们确实会播放。

### skipoff

退出“跳过直到下一个选择”和“自动模式”。

### filelog
```
filelog
```
这允许创建文件日志。

程序使用的每个资源都会作为标签记录在该文件日志中。

如果您既没有指定此命令，也没有指定globalon，那么nscr.exe将不会生成任何内容，因此将允许从CD运行。

### globalon
```
globalon
```
打开全局变量的使用。 如果您启用此或文件记录，nscr.exe将无法运行受写保护的媒体。

### labellog

　此命令的行为有点像[filelog](#filelog)，但在这种情况下，它保留了标签记录。

每当调用[goto](#goto)或[gosub](#gosub)命令或类似的东西时，如果指定了[labellog](#labellog)，将存储调用标签的记录。

### savenumber
```
savenumber <number>
```
更改保存文件数量的限制。 最多可以是20，默认为9。

如果您不小心确保保存菜单不会从屏幕限制中溢出（使用[menowsetwindow](#menowsetwindow)），此命令可能会导致解释器硬崩溃，因此请小心。

### savegame
```
savegame <save number>
```
　将游戏保存在该保存号码中。 由于这不需要确认，请小心。
　
### loadgame
```
loadgame <save number>
```
　加载与保存编号相对应的保存数据。 由于它没有提示确认，所以要小心。

如果无法加载保存，此命令不会给出错误指示，并继续下一个命令而不停止。
　
### savefileexist
```
savefileexist <numerical variable>,<save number>
```
　如果保存文件存在，则返回1，如果没有保存文件，则返回0。
　
### saveon

重新打开保存模式（有关更多详细信息，请参阅[save](#save)）。

### saveoff

关闭保存模式。

这并不意味着您无法保存，这意味着当您加载时，玩家开始的位置将位于定义saveon而不是保存的最后一个位置。

你为什么要关闭保存模式？ 当保存模式打开时，它会记录加载到日志中的每个精灵——当您尝试进行快速动画时，会造成中度到大规模的减速。 在这些情况下，您绝对应该在开始动画之前调用saveoff，然后在完成后直接调用saveon。

### mesbox
```
mesbox <character string>,<character string>
```
显示一个消息框。

第一个字符串是框的内容，第二个字符串是该框的标题。

### inputstr
```
inputstr <character variable>,<character string>,<number>,{0,1}(,<number>,<number>,<number>,<number>)
```
创建一个输入对话框，捕获字符变量的所有输入。

字符串用作对话框消息文本。

第一个数字是最大输入长度，第二个数字（0或1）确定用户是否被迫输入2字节字符，最后4个可以省略，但按顺序（窗口大小x），（窗口大小y），（文本输入窗口大小x），（文本输入窗口大小y）。

### input
```
input <character variable>,"explanation text","default string", <character limit>,<2-byte flag>
```
呈现一个文本输入框，非常类似于inputstr。 然而，与inputstr不同，输入必须具有默认字符字符串。

根据2字节标志是0还是1，您可以强制用户输入2字节字符。

### clickpos
```
clickpos <numerical variable>,<numerical variable>
```
返回最后一次点击的位置——第一个变量是x，第二个变量是y。

### systemcall
```
systemcall <function>
```
工作原理与系统菜单相同。

如果您将其用于select/selgosub等内容，那么您最终会得到与标题屏幕没有太大区别的东西。

（在这种情况下，最好通过rmode暂时关闭右键单击菜单功能）

可用的命令与rmenu使用的命令完全相同。

如果您调用“systemcall rmenu”，这与调用右键单击菜单本身相同。

当您希望在按钮等待状态下右键单击菜单功能时，您会使用此功能。 退出此右键单击菜单后，解释器将继续执行系统调用命令下方的一行。

（这可能会使屏幕和解释器堆栈处于不一致的状态，因此使用此命令时要小心。）

### automode(mode_ext)

这是一个专门为商业软件“Gin'iro”开发的命令。 当您使用此命令时，您可以从菜单中输入自动模式。 它在概念上类似于“跳到下一个选择”选项，但它显示字符的速度要慢得多（延迟由automode_time定义）。 因此，这几乎就像计算机向您读取文本的模式。

当自动模式仍在进行时，您可以从菜单中有效地调整声音播放音量（MP3（BGM）语音（DWAVE 0）SE（DWAVE 1～）仍然处于活动状态并可调）。

未来计划为此命令添加更多功能，并使事情更严格地符合预定义的语法。
### automode_time
```
automode_time <number>
```
当处于automode(mode_ext)时，当文本显示不是即时的时，这会以毫秒为单位设置字符之间的延迟。

### defvoicevol
```
defvoicevol <number>
```
设置语音的默认音量（DWAVE 0）。 范围从0到100。 默认值为100。

### defsevol
```
defsevol <number>
```
设置声音效果的默认音量（DWAVE 1+）。 范围从0到100。 默认情况下是100。

### defmp3vol
```
defmp3vol <number>
```
设置mp3的默认音量，范围为0-100。 默认情况下是100。

### mode_saya

专门为同人游戏编写的命令模式，“Saya～Labyrinth of Immorality～”。 指定此命令后，您将进入：传奇的Saya模式！

在Saya模式下：

当文本窗口消失时，精灵0-9也会消失，无论它们是否被标记为可见。

当文本窗口消失时，文本窗口下方指示状态的栏和数字也会消失。

您将做这两件事，例如，当您有一个参数状态窗口时，当文本窗口消失时，您想隐藏该窗口。

### mode800
```
;mode800
```
启用800x600屏幕模式（是的，;一开始是必要的！）。 此命令必须是0.txt中的第一行，甚至高于*define。
```
　　;mode800
　　*define
```

### soundpressplgin
```
soundpressplgin <character string>
```
使用此功能，您可以指定一个dll文件，用于解码非mp3的其他类型的压缩声音文件。 字符串的用法是“插件名称|3字符文件扩展名”。
```
soundpressplgin "nbzplgin.dll|nbz"
```

### spi
```
spi <character string>
```
允许使用图像压缩插件dll——因此适用于支持nscripter不支持的图像文件类型。 字符串的用法是“plugin dll name|file extension”。
```
　　　spi "jpgplgin.dll|jpg"
　　　spi "iflf2.spi|lf2"
```

### arc
```
arc <character string>
```
指定归档解压缩插件。

字符串的形式是“<archive name>|<plugin dll name>”。

虽然它会解压声音、音乐和图像，但它不会运行脚本。
```
　　　arc "arc.sar|scrunarc.dll"
```
通过将其与注册表读取命令相结合，您可以做很多事情。 例如，您可以非常轻松地读取注册表，发现机器安装了“To Heart”，并指定适当的存档进行相应的解压缩。

（样本来源）
getreg $0,"software\leaf\toheart","datadir"
add $0,"\lvns3dat.pak|axlfpak.spi"
arc $0

### nsa

允许NSA归档模式。 在此模式下，可以从与可执行文件本身位于同一目录中的nsa*.arc读取BMP等资源。 nsa*.arc文件本身由nsaarc.exe生成，该文件可在SDK中找到。

请注意，您可以连续命名文件arc.nsa arc1.nsa arc2.nsa～arc9.nsa，就解释器而言，它们都将被视为同一命名空间的一部分——就好像它是一个大存档一样。 您可以使用它来快速拆包和重新打包存档以进行测试。

### nsadir
```
nsadir "foldername"
```
设置nsa存档的文件夹搜索路径。 默认情况下，这与可执行文件本身是同一个目录。

### versionstr
```
versionstr <character string 1>,<character string 2>
```
指定要在关于对话框中显示的版本字符串。 第一个字符串是第一行，第二个字符串是第二行。

### caption
```
caption <character string>
```
设置窗口标题。

### date
```
date <variable 1>,<variable 2>,<variable 3>
```
返回当前日期。 变量1是年份，变量2是月份，变量3是日期。

### time
```
time <variable 1>,<variable 2>,<variable 3>
```
获取当前时间；变量1是小时，变量2是分钟，变量3是秒。

### savetime
```
savetime <save number>,%month,%day,%hours,%minutes
```

获取记录特定保存的月份、日期、小时和小时的分钟数。

如果保存文件不存在，则%month参数设置为0。
```
savetime 3,%0,%1,%2,%3
if %0=0 goto *non
`Save 3 was recorded on %0 / %1, %2 : %3.@
end
*non
`Save 3 nonexistent.@
end
```

### getversion
```
getversion <numerical variable>
```
获取当前版本字符串。 作为3位数返回；例如，1.90版本将作为190返回。

### getreg
```
getreg <character variable>,<character string>,<variable name>
```
打开注册表并查询变量。

只会在HKEY_CURRENT_USER中搜索。
```
　　　　getreg $0,"software\leaf\toheart","datadir"
```
　　
### getini
```
getini <character variable>,<character string>,<character string>,<character string>
```
打开一个ini文件并读取变量。 按顺序，字符串是：ini文件名、节名、键名。

### killmenu
```
killmenu <number>
```
这会删除从左到右计数的菜单项。 现在，一旦你删除了一个菜单项，所有菜单项向移动序号，所以请小心。0是最左边的项目，0+x是最左边的项目x。

### defaultspeed
```
defaultspeed <number>,<number>,<number>
```
为解释器遇到特殊字符串时指定文本速度!sd。

从左到右，这些是菜单中的“慢”、“默认”和“快速”。

### !sd
```
!sd
```
将文本显示设置为默认速度。 您可以使用defaultspeed命令设置默认速度本身。

### menu_full
```
menu_full
```
进入全屏模式。

### menu_window
```
menu_window
```
进入窗口模式。

### menu_click_def
```
menu_click_def
```
定义默认文本显示模式。

### menu_click_page
```
menu_click_page
```
切换一次显示页面上所有文本的模式。

