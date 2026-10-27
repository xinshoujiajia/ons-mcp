# 命令集统计报告

- 游戏目录：`D:\game\美少女万华镜2`
- 脚本：`0.txt`（GBK，28,646 行）
- 引擎基线：ONScripter-Jh LUT 347 条 / OnscripterYuri LUT 348 条（Yuri ⊃ Jh，实际多 1 条 `effectskip`）

## 1. 脚本行分类

| 类别 | 行数 |
|---|---|
| 文本行（对话/旁白，行首为双字节字符） | 13,383 |
| 注释 `;` | 360 |
| 标签 `*xxx` | 264 |
| 控制行（`~` 等） | 1 |
| 无法归类 | 0 |
| 空行 | 148 |
| **合计** | 28,646 |

标签数 **264**，`defsub` 自定义指令 **41** 条。

## 2. 命令使用分布（按阶段）

| 阶段 | 命令种类 | 语句行数 | 含义 |
|---|---|---|---|
| P1 | 67 | 6,516 | 第一阶段：最小可跑（文本/bg/点击推进） |
| P2 | 14 | 359 | 第二阶段：完整流程（分支/选项/存档） |
| P3 | 14 | 6,050 | 第三阶段：图像完整（立绘/合成） |
| P4 | 12 | 34 | 第四阶段：兼容加固 |
| — | 21 | 1,531 | 本期不实现（音频/视频/动画/UI 细节） |

## 3. 游戏实际使用的命令（全量，按频次）

> `引擎` 列：✔ = 引擎 LUT 中的原生命令；defsub = 脚本自定义宏（需跟着它的实现走）。

| # | 命令 | 次数 | 类别 | 阶段 | 引擎 | 样例 |
|---|---|---|---|---|---|---|
| 1 | `chara01` | 3,929 | 游戏宏(defsub) | P3 | 宏 | `chara01 "file4","A181"` |
| 2 | `bg01` | 1,810 | 游戏宏(defsub) | P1 | 宏 | `bg01 "file","ev/w03_02_1_001":mov %read_cgdata01,1` |
| 3 | `bg` | 1,254 | 图像 | P1 | ✔ | `bg "cut/cut030.png",10,800` |
| 4 | `chara02` | 817 | 游戏宏(defsub) | P3 | 宏 | `chara02 "file4","04A174"` |
| 5 | `if` | 799 | 流程控制 | P1 | ✔ | `if %sceneon=1 goto *scene_mode` |
| 6 | `se01` | 694 | 游戏宏(defsub) | — | 宏 | `se01 "file","se102"` |
| 7 | `lsp` | 666 | 图像 | P3 | ✔ | `lsp 998,":a/20,50,0;bg3/xt.png",0,0:print 1` |
| 8 | `print` | 578 | 图像 | P1 | ✔ | `print 1` |
| 9 | `numalias` | 425 | 变量运算 | P1 | ✔ | `numalias save_data_y,66` |
| 10 | `chara03` | 407 | 游戏宏(defsub) | P3 | 宏 | `chara03 "file4","28A15A903"` |
| 11 | `screen_clear_menu` | 234 | 游戏宏(defsub) | P1 | 宏 | `screen_clear_menu` |
| 12 | `vsp` | 232 | 图像 | P1 | ✔ | `vsp 600,0` |
| 13 | `bgmstop` | 226 | 音频 | — | ✔ | `bgmstop` |
| 14 | `music` | 218 | 游戏宏(defsub) | — | 宏 | `music "file","wbgm01"` |
| 15 | `sentence` | 199 | 游戏宏(defsub) | P1 | 宏 | `sentence "cut"` |
| 16 | `gosub` | 168 | 流程控制 | P2 | ✔ | `gosub *wanhuatong` |
| 17 | `csp` | 160 | 图像 | P1 | ✔ | `csp 998` |
| 18 | `qlie_flash` | 143 | 游戏宏(defsub) | — | 宏 | `qlie_flash` |
| 19 | `return` | 142 | 流程控制 | P1 | ✔ | `return` |
| 20 | `mov` | 127 | 变量运算 | P1 | ✔ | `mov $sentence,"ysr000"` |
| 21 | `lsph` | 97 | 图像 | P3 | ✔ | `lsph 597,":a/60,80,0;movie/movie029.png",0,0:print 1` |
| 22 | `goto` | 90 | 流程控制 | P1 | ✔ | `goto *define` |
| 23 | `wait` | 74 | 系统/UI | P1 | ✔ | `wait 1000` |
| 24 | `for` | 68 | 流程控制 | P1 | ✔ | `for %sub1= 0 to 5 step 1` |
| 25 | `next` | 68 | 流程控制 | P1 | ✔ | `next` |
| 26 | `btn` | 59 | 系统/UI | P2 | ✔ | `btn 41,0,75,1280,720-75,0,0` |
| 27 | `quakey` | 58 | 动画特效 | — | ✔ | `quakey 3,500` |
| 28 | `allspresume` | 57 | 图像 | P3 | ✔ | `allspresume;所有使用allsphide隐藏的图片再显示` |
| 29 | `se02` | 51 | 游戏宏(defsub) | — | 宏 | `se02 "loop","infinity"` |
| 30 | `movie01` | 45 | 游戏宏(defsub) | — | 宏 | `movie01 "13","movie/movie012"` |
| 31 | `exbtn` | 44 | 系统/UI | P2 | ✔ | `exbtn 100,100,"c100p200p300c301c302c303c304S1,(cgsys/title/S` |
| 32 | `defsub` | 41 | 变量运算 | P1 | ✔ | `defsub bg01;背景1(底层)` |
| 33 | `quakex` | 29 | 动画特效 | — | ✔ | `quakex 3,200` |
| 34 | `itoa` | 28 | 变量运算 | P1 | ✔ | `itoa $sub2,%sub1` |
| 35 | `bg02` | 27 | 游戏宏(defsub) | P1 | 宏 | `bg02 "rep0","eyecatch/eyecatch002"` |
| 36 | `getparam` | 24 | 变量运算 | P1 | ✔ | `getparam $face_ctrl,$face` |
| 37 | `amsp` | 21 | 图像 | P1 | ✔ | `amsp 997,0,0` |
| 38 | `btnwait` | 21 | 系统/UI | P2 | ✔ | `btnwait %bwait` |
| 39 | `effect` | 20 | 动画特效 | — | ✔ | `effect 10,10,600;10透明渐变600` |
| 40 | `chara05` | 17 | 游戏宏(defsub) | P3 | 宏 | `chara05 "file4","43A15A1001"` |
| 41 | `ef01` | 16 | 游戏宏(defsub) | P3 | 宏 | `ef01 "file","bg3/bg062"` |
| 42 | `spbtn` | 16 | 系统/UI | P2 | ✔ | `spbtn 297,297` |
| 43 | `screen_clear_menu1` | 15 | 游戏宏(defsub) | P1 | 宏 | `screen_clear_menu1` |
| 44 | `add` | 15 | 变量运算 | P1 | ✔ | `add %savepicy, save_height` |
| 45 | `btndef` | 14 | 系统/UI | P2 | ✔ | `btndef clear` |
| 46 | `chara04` | 13 | 游戏宏(defsub) | P3 | 宏 | `chara04 "file4","25A3302"` |
| 47 | `msp` | 13 | 图像 | P3 | ✔ | `msp 998,0,150` |
| 48 | `dwave` | 10 | 音频 | — | ✔ | `dwave 0,"voice/"+$Voice+".ogg":ead_cgdata55,1;有语音播放语音后返回` |
| 49 | `getspsize` | 10 | 图像 | P3 | ✔ | `getspsize 601,%chara01_sp_X,%chara01_sp_Y;获取立绘大小` |
| 50 | `split` | 10 | 变量运算 | P4 | ✔ | `split $%sub1,",",$savemonth,$saveday,$savehour,$saveminute,$` |
| 51 | `bgmvol` | 9 | 音频 | — | ✔ | `bgmvol 0` |
| 52 | `exbtn_d` | 9 | 系统/UI | P2 | ✔ | `exbtn_d "p100-105c200-205";c300-305"` |
| 53 | `getpage` | 8 | 系统/UI | P1 | ✔ | `getpage` |
| 54 | `btndown` | 7 | 系统/UI | P2 | ✔ | `btndown 1` |
| 55 | `textoff` | 6 | 文本 | P1 | ✔ | `textoff:vsp 299,0:print 1` |
| 56 | `csel` | 6 | 系统/UI | P2 | ✔ | `csel "射在里面",*L_w_08_04_sel1_0,"射在外面",*L_w_08_04_sel1_1` |
| 57 | `dwavestop` | 6 | 音频 | — | ✔ | `dwavestop 0` |
| 58 | `windoweffect` | 6 | 动画特效 | — | ✔ | `windoweffect 10,200;文本框显示／消失的时候的效果` |
| 59 | `spstr` | 6 | 系统/UI | P2 | ✔ | `spstr "c100-109c200-209c300-309"` |
| 60 | `getmousepos` | 6 | 系统/UI | P1 | ✔ | `getmousepos %cursorx,%cursory` |
| 61 | `isdown` | 6 | 系统/UI | P1 | ✔ | `isdown %sub1` |
| 62 | `itoa2` | 6 | 变量运算 | P1 | ✔ | `itoa2 $sub1,%savedatanow` |
| 63 | `bgm` | 5 | 音频 | — | ✔ | `bgm "sound/se387.ogg"` |
| 64 | `getcselstr` | 5 | 系统/UI | P2 | ✔ | `getcselstr $select00,0` |
| 65 | `len` | 4 | 变量运算 | P1 | ✔ | `len %name2,$Name;获取名字长度` |
| 66 | `bar` | 4 | 系统/UI | P4 | ✔ | `bar 0,1,730+480,%backlogbary,16,%backlogbarone2,1,#DDDDDD` |
| 67 | `cell` | 4 | 图像 | P3 | ✔ | `cell %sub1+510,0` |
| 68 | `erasetextwindow` | 3 | 文本 | P1 | ✔ | `erasetextwindow 1` |
| 69 | `texton` | 3 | 文本 | P1 | ✔ | `texton` |
| 70 | `texec` | 3 | 文本 | P1 | ✔ | `texec` |
| 71 | `barclear` | 3 | 系统/UI | P4 | ✔ | `barclear` |
| 72 | `savefileexist` | 3 | 系统/UI | P4 | ✔ | `savefileexist %sub1,100` |
| 73 | `screen_clear_leave` | 3 | 游戏宏(defsub) | P1 | 宏 | `screen_clear_leave` |
| 74 | `checkpage` | 3 | 系统/UI | P4 | ✔ | `checkpage %sub1,1` |
| 75 | `cellcheckspbtn` | 3 | 系统/UI | P4 | ✔ | `cellcheckspbtn %sub6,%sub6` |
| 76 | `text_nomal` | 2 | 游戏宏(defsub) | P1 | 宏 | `text_nomal` |
| 77 | `qlie_flash1` | 2 | 游戏宏(defsub) | — | 宏 | `qlie_flash1` |
| 78 | `quake` | 2 | 动画特效 | — | ✔ | `quake 3,200` |
| 79 | `char1` | 2 | 引擎未提供(降级跳过) | — | 缺 | `char1 48,650,"A30_A20_1_.png"` |
| 80 | `mp3` | 2 | 音频 | — | ✔ | `mp3 "bgm/ed.ogg"` |
| 81 | `setlayer` | 2 | 系统/UI | P4 | ✔ | `setlayer 0,100,"hana.dll"` |
| 82 | `dim` | 2 | 变量运算 | P2 | ✔ | `dim ?savecache[save_num]` |
| 83 | `setwindow3` | 2 | 图像 | P1 | ✔ | `setwindow3 300,600,32,3,26,26,0,10,1,1,1,"cgsys/sys/windowfr` |
| 84 | `strsp` | 2 | 图像 | P3 | ✔ | `strsp 301+%sub1,"",80,0,32,4,20,20,0,10,1,1,#FFFFFF` |
| 85 | `mid` | 2 | 变量运算 | P4 | ✔ | `mid $savetextget,$savetextget,0,88` |
| 86 | `allsphide` | 2 | 图像 | P3 | ✔ | `allsphide` |
| 87 | `overlap_long` | 1 | 引擎未提供(降级跳过) | — | 缺 | `overlap_long` |
| 88 | `screen_clear` | 1 | 游戏宏(defsub) | P1 | 宏 | `screen_clear` |
| 89 | `gettag` | 1 | 文本 | P1 | ✔ | `gettag $Voice,$Name,$face;获取[]内的文本并根据"/"分成3份` |
| 90 | `mul` | 1 | 变量运算 | P1 | ✔ | `mul %name2,15;长度乘以15` |
| 91 | `div` | 1 | 变量运算 | P1 | ✔ | `div %name2,2;再除以2就获得了名字文本左上x坐标偏移(根据文字大小.这里是30号)` |
| 92 | `caption` | 1 | 系统/UI | P1 | ✔ | `caption "美少女万华镜2 ONS移植版 青桔移植组 v1.0 "` |
| 93 | `nsa` | 1 | 系统/UI | P1 | ✔ | `nsa;读取nsa压缩包` |
| 94 | `rubyon` | 1 | 文本 | P4 | ✔ | `rubyon;注音模式` |
| 95 | `pretextgosub` | 1 | 文本 | P1 | ✔ | `pretextgosub *pretext_do;文本前的名字,语音和头像处理` |
| 96 | `textgosub` | 1 | 文本 | P1 | ✔ | `textgosub *text_btn;文本处理` |
| 97 | `loadgosub` | 1 | 流程控制 | — | ✔ | `loadgosub *load_config;读档处理` |
| 98 | `globalon` | 1 | 系统/UI | P1 | ✔ | `globalon;全局变量开启` |
| 99 | `usewheel` | 1 | 系统/UI | P1 | ✔ | `usewheel;使用鼠标滚轮上(-2)和下(-3)` |
| 100 | `useescspc` | 1 | 系统/UI | P1 | ✔ | `useescspc;使用ESC键(-10)和空格(-11)` |
| 101 | `maxkaisoupage` | 1 | 系统/UI | P1 | ✔ | `maxkaisoupage 100;最大历史文本行数` |
| 102 | `automode` | 1 | 系统/UI | P1 | ✔ | `automode;启用自动模式,语音读完才会下一句文本(仅支持dwave 0和dwave 1)` |
| 103 | `humanz` | 1 | 系统/UI | P1 | ✔ | `humanz 590;图片与文本框顺序,比590大的,会在文本框后面` |
| 104 | `windowback` | 1 | 系统/UI | P1 | ✔ | `windowback;与上面的一同使用` |
| 105 | `transmode` | 1 | 系统/UI | P1 | ✔ | `transmode alpha;图片透明形式,一般png都是alpha` |
| 106 | `shadedistance` | 1 | 系统/UI | P1 | ✔ | `shadedistance 1,2;阴影` |
| 107 | `linepage` | 1 | 文本 | P1 | ✔ | `linepage;将行末没有\的显示文本的换行视为换页` |
| 108 | `game` | 1 | 系统/UI | P1 | ✔ | `game` |
| 109 | `lookbackflush` | 1 | 系统/UI | P1 | ✔ | `lookbackflush` |
| 110 | `delay` | 1 | 系统/UI | P1 | ✔ | `delay 1500` |
| 111 | `rnd` | 1 | 变量运算 | P2 | ✔ | `rnd %sub10,3` |
| 112 | `saveoff` | 1 | 系统/UI | P1 | ✔ | `saveoff` |
| 113 | `getcselnum` | 1 | 系统/UI | P2 | ✔ | `getcselnum %selectnum` |
| 114 | `gettext` | 1 | 文本 | P1 | ✔ | `gettext $savetextget` |
| 115 | `getscreenshot` | 1 | 系统/UI | P1 | ✔ | `getscreenshot 178,100` |
| 116 | `automode_time` | 1 | 系统/UI | P1 | ✔ | `automode_time %sub1*%textspeed+%autotime` |
| 117 | `ispage` | 1 | 系统/UI | P1 | ✔ | `ispage %textkai` |
| 118 | `getcursorpos` | 1 | 系统/UI | P1 | ✔ | `getcursorpos %textlastx,%textlasty` |
| 119 | `getenter` | 1 | 系统/UI | P1 | ✔ | `getenter` |
| 120 | `getcursor` | 1 | 系统/UI | P1 | ✔ | `getcursor` |
| 121 | `textbtnwait` | 1 | 文本 | P1 | ✔ | `textbtnwait %bwait` |
| 122 | `saveon` | 1 | 系统/UI | P1 | ✔ | `saveon` |
| 123 | `inc` | 1 | 变量运算 | P1 | ✔ | `inc %backlogtotal` |
| 124 | `sub` | 1 | 变量运算 | P1 | ✔ | `sub %sub4, backlog_height` |
| 125 | `savescreenshot2` | 1 | 系统/UI | P4 | ✔ | `savescreenshot2 $savescreen` |
| 126 | `savegame` | 1 | 系统/UI | P4 | ✔ | `savegame %savedatanow` |
| 127 | `savetime` | 1 | 系统/UI | P4 | ✔ | `savetime %savedatanow,%savemonth,%saveday,%savehour,%savemin` |
| 128 | `es_snd_stop` | 1 | 游戏宏(defsub) | — | 宏 | `es_SND_STOP:stop` |

## 3.1 第一阶段要落地的命令（P1）

原生命令 59 条：

```
bg(1254)  if(799)  print(578)  numalias(425)  vsp(232)  csp(160)
return(142)  mov(127)  goto(90)  wait(74)  for(68)  next(68)
defsub(41)  itoa(28)  getparam(24)  amsp(21)  add(15)  getpage(8)
textoff(6)  getmousepos(6)  isdown(6)  itoa2(6)  len(4)  erasetextwindow(3)
texton(3)  texec(3)  setwindow3(2)  gettag(1)  mul(1)  div(1)
caption(1)  nsa(1)  pretextgosub(1)  textgosub(1)  globalon(1)  usewheel(1)
useescspc(1)  maxkaisoupage(1)  automode(1)  humanz(1)  windowback(1)  transmode(1)
shadedistance(1)  linepage(1)  game(1)  lookbackflush(1)  delay(1)  saveoff(1)
gettext(1)  getscreenshot(1)  automode_time(1)  ispage(1)  getcursorpos(1)  getenter(1)
getcursor(1)  textbtnwait(1)  saveon(1)  inc(1)  sub(1)
```

宏（defsub，解释器执行宏体即可，不需要单独实现）8 条：

```
bg01(1810)  screen_clear_menu(234)  sentence(199)  bg02(27)  screen_clear_menu1(15)  screen_clear_leave(3)
text_nomal(2)  screen_clear(1)
```

> 宏里调用的底层原语如果不实现，宏会半途降级；所以 P1 的判据是「这一组原语能跑通 text_nomal / bg01 / bg02 这三个宏」。

## 4. 引擎提供但本游戏未使用（241 条，本期不实现）

```
abssetcursor      addkinsoku        allsp2hide        allsp2resume      amsp2             arc               atoi              autoclick
autosaveoff       avi               bclear            bcursor           bdef              bdown             bexec             bgcopy
bgcpy             bgmfadein         bgmfadeout        bgmonce           blt               br                break             bsp
btime             btntime           btntime2          btnwait2          btrans            cellcheckexbtn    checkkey          chvol
cl                click             clickstr          clickvoice        cmp               cos               cselbtn           cselgoto
csp2              date              dec               defaultfont       defaultspeed      definereset       defmp3vol         defsevol
defvoicevol       deletescreenshot  draw              drawbg            drawbg2           drawclear         drawfill          drawsp
drawsp2           drawsp3           drawtext          dwaveload         dwaveloop         dwaveplay         dwaveplayloop     effectblank
effectcut         end               english           exec_dll          existspbtn        fileexist         filelog           flushout
getbgmvol         getbtntimer       getcursorpos2     getfunction       getinsert         getlog            getlogtext        getmclick
getmouseover      getmp3vol         getpageup         getparam2         getreg            getret            getsavestr        getsevol
getspmode         getsppos          gettab            gettaglog         gettimer          getversion        getvoicevol       getzxc
humanorder        indent            input             intlimit          isfull            isskip            jumpb             jumpf
kidokumode        kidokuskip        kinsoku           labellog          layermessage      ld                linepage2         loadgame
locate            logsp             logsp2            lookbackbutton    lookbackcolor     lookbacksp        loopbgm           loopbgmstop
lr_trap           lrclick           lsp2              lsp2add           lsp2sub           lsph2             lsph2add          lsph2sub
luacall           luasub            menu_automode     menu_click_def    menu_click_page   menu_full         menu_window       menuselectcolor
menuselectvoice   menusetwindow     mod               mode_ext          mode_saya         mode_wave_demo    monocro           mov10
mov3              mov4              mov5              mov6              mov7              mov8              mov9              movemousecursor
movie             movl              mp3fadein         mp3fadeout        mp3loop           mp3save           mp3stop           mp3vol
mpegplay          msp2              nega              nextcsel          notif             ns2               ns3               nsadir
ofscopy           ofscpy            okcancelbox       pagetag           play              playonce          playstop          prnum
prnumclear        puttext           repaint           reset             resettimer        rmenu             rmode             rnd2
roff              rubyoff           sar               savedir           savegame2         savename          savenumber        savepoint
savescreenshot    select            selectbtnwait     selectcolor       selectvoice       selgosub          selnum            setcursor
setkinsoku        setwindow         setwindow2        sevol             sin               skip              skipoff           soundpressplgin
sp_rgb_gradation  spclclk           spi               splitstring       spreload          stop              stralias          strsph
systemcall        tablegoto         tal               tan               tateyoko          textclear         textcolor         texthide
textshow          textspeed         textspeeddefault  time              transbtn          trap              underline         versionstr
voicevol          vsp2              waittimer         wave              waveloop          wavestop          windowchip        yesnobox
zenkakko
```
