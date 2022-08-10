# -*- coding:utf-8 -*-
# Author: 张来吃
# Version: 1.0.0
# Contact: laciechang@163.com

# 感谢 Igor Ridanovic 提供的时间码转换方法
# https://github.com/IgorRidanovic/smpte

# -----------------------------------------------------
# 本工具仅支持在达芬奇内运行
# -----------------------------------------------------


RESOLVE_FPS_MAPPING = {             # 虽然很奇怪但是得问问BMD为什么会有这种神奇的帧率表达方式
    '16': 16.0,     '18': 18.0,
    '23': 23.976,   '24': 24.0,   '24.0': 24.0,
    '25.0': 25.0,   '25': 25.0,     '29': 29.97,
    '30': 30.0,     '30.0': 30.0,     '47': 47.952,
    '48': 48.0,     '50': 50.0,
    '59': 59.94,    '60': 60.0,
    '72': 72.0,     '95': 95.904,
    '96': 96.0,     '100': 100.0,
    '119': 119.88,  '120': 120.0
}

class SMPTE(object):
	'''Frames to SMPTE timecode converter and reverse.'''
	def __init__(self):
		self.fps = 24
		self.df  = False


	def getframes(self, tc):
		'''Converts SMPTE timecode to frame count.'''

		if int(tc[9:]) > self.fps:
			raise ValueError ('SMPTE timecode to frame rate mismatch.', tc, self.fps)

		hours   = int(tc[:2])
		minutes = int(tc[3:5])
		seconds = int(tc[6:8])
		frames  = int(tc[9:])

		totalMinutes = int(60 * hours + minutes)

		# Drop frame calculation using the Duncan/Heidelberger method.
		if self.df:
			dropFrames = int(round(self.fps * 0.066666))
			timeBase   = int(round(self.fps))
			hourFrames   = int(timeBase * 60 * 60)
			minuteFrames = int(timeBase * 60)
			frm = int(((hourFrames * hours) + (minuteFrames * minutes) + (timeBase * seconds) + frames) - (dropFrames * (totalMinutes - (totalMinutes // 10))))
		# Non drop frame calculation.
		else:
			self.fps = int(round(self.fps))
			frm = int((totalMinutes * 60 + seconds) * self.fps + frames)

		return frm


	def gettc(self, frames):
		'''Converts frame count to SMPTE timecode.'''

		frames = abs(frames)

		# Drop frame calculation using the Duncan/Heidelberger method.
		if self.df:

			spacer = ':'
			spacer2 = ';'

			dropFrames         = int(round(self.fps * .066666))
			framesPerHour      = int(round(self.fps * 3600))
			framesPer24Hours   = framesPerHour * 24
			framesPer10Minutes = int(round(self.fps * 600))
			framesPerMinute    = int(round(self.fps) * 60 - dropFrames)

			frames = frames % framesPer24Hours

			d = frames // framesPer10Minutes
			m = frames % framesPer10Minutes

			if m > dropFrames:
				frames = frames + (dropFrames * 9 * d) + dropFrames * ((m - dropFrames) // framesPerMinute)
			else:
				frames = frames + dropFrames * 9 * d

			frRound = int(round(self.fps))
			hr = int(frames // frRound // 60 // 60)
			mn = int((frames // frRound // 60) % 60)
			sc = int((frames // frRound) % 60)
			fr = int(frames % frRound)

		# Non drop frame calculation.
		else:
			self.fps = int(round(self.fps))
			spacer  = ':'
			spacer2 = spacer

			frHour = self.fps * 3600
			frMin  = self.fps * 60

			hr = int(frames // frHour)
			mn = int((frames - hr * frHour) // frMin)
			sc = int((frames - hr * frHour - mn * frMin) // self.fps)
			fr = int(round(frames -  hr * frHour - mn * frMin - sc * self.fps))

		# Return SMPTE timecode string.
		return(
				str(hr).zfill(2) + spacer +
				str(mn).zfill(2) + spacer +
				str(sc).zfill(2) + spacer2 +
				str(fr).zfill(2)
				)


class Resolve():
    def __init__(self) -> None:
        self.resolve = bmd.scriptapp('Resolve')
        self.projectmanager = self.resolve.GetProjectManager()
        self.mediastorage = self.resolve.GetMediaStorage()
        self.currentproject = self.projectmanager.GetCurrentProject()
        self.mediapool = self.currentproject.GetMediaPool()
        self.timeline = self.currentproject.GetCurrentTimeline()


resolve = Resolve()
fu = bmd.scriptapp('Fusion')
ui = fu.UIManager
disp = bmd.UIDispatcher(ui)

fps = str(resolve.timeline.GetSetting('timelineFrameRate'))
smpte = SMPTE()
smpte.fps = RESOLVE_FPS_MAPPING[fps]
smpte.df = bool(int(resolve.timeline.GetSetting('timelineDropFrameTimecode')))

Header = {
    0: {'name': 'Frame', 'width': 100}, 
    1: {'name': 'Record TC', 'width': 150},
}

def getTracklistbyCount(track_num) -> list:
    return resolve.timeline.GetItemListInTrack('Video', track_num)

def getInlist(tracklist):
    return (int(i.GetStart()) for i in tracklist)

def getOutlist(tracklist):
    return (int(i.GetEnd()) for i in tracklist)

def getAllclipinfo():
    info = {}
    count = int(resolve.timeline.GetTrackCount('Video'))
    for i in range(1, count+1):
        inlist = list(getInlist(getTracklistbyCount(i)))
        inlist = inlist + list(getOutlist(getTracklistbyCount(i)))
        info[i] = inlist
    return info

def markIntimeline(point, treeitem):
    row = treeitem.NewItem()
    row.Text[0] = str(point)
    row.Text[1] = frameToRTC(point)
    treeitem.AddTopLevelItem(row)

def frameToRTC(frame):
    return smpte.gettc(frame)

def compareInpoint(interval, tree):
    info = getAllclipinfo()
    count = int(resolve.timeline.GetTrackCount('Video'))
    result = []
    for i in range(1, count+1):
        inlist = info[i]
        for j in inlist:
            for k in range(1, count+1):
                target = info[k]
                source = j - interval
                if source in target:
                    if j not in result:
                        result.append(j)
                        markIntimeline(j, tree)
    return result

def buildHeader(treeitem):
    header = treeitem.NewItem()
    treeitem.SetHeaderItem(header)
    for i in range(0, len(Header)):
        info = Header[i]
        header.Text[i] = info['name']
        treeitem.ColumnWidth[i] = info['width']

Cliptree = 'Cliptree'
CheckRange = 'CheckRange'
Run = 'Run'
Status = 'Status'

window = [ui.VGroup([
    ui.Label({"Text": "<a href='http://www.baidu.com' style='color: #FA5B4A; text-decoration: none'>错帧检查</a>", "Alignment": {"AlignHCenter": True, "AlignVCenter": True}, "Weight": 0.1, "OpenExternalLinks" : True,}),
    ui.Tree({"ID": Cliptree}),
    ui.HGroup({"Weight": 0, "StyleSheet": "max-height:30px"}, [
        ui.Label({"Text": "阈值",  "Weight": 0}),
        ui.SpinBox({"ID": CheckRange, "Value": 2, "Minimum": 1, "Maximum": 99, "SingleStep": 1}),
        ui.HGap(),
        ui.Label({"ID": Status,"StyleSheet": "min-width:80px", "Weight": 0 }),
        ui.Button({"ID": Run, "Text": "检查", "Weight": 0}),
    ]),
])]

dlg = disp.AddWindow({ 
                        "WindowTitle": "Flash Frame Checker", 
                        "ID": "MyWin", 
                        "Geometry": [ 
                                    600, 300, # position when starting
                                    400, 300 #width, height
                         ], 
                        }, window)

itm = dlg.GetItems()
def _closewindow(ev):
    disp.ExitLoop()

def _run(ev):
    itm[Cliptree].Clear()
    checkrange = itm[CheckRange].Value
    totalCount = 0
    for interv in range(1, checkrange+1):
        res = compareInpoint(interv, itm[Cliptree])
        totalCount += len(res)
    itm[Status].Text = '找到 %s 个结果'%(str(totalCount))

def _jump_to_target_clip(ev):
    timecode = itm[Cliptree].CurrentItem().Text[1]
    resolve.timeline.SetCurrentTimecode(timecode)

buildHeader(itm[Cliptree])

dlg.On['MyWin'].Close = _closewindow
dlg.On[Cliptree].ItemClicked = _jump_to_target_clip
dlg.On[Run].Clicked = _run

if __name__ == '__main__':
    dlg.Show()
    disp.RunLoop()
    dlg.Hide()