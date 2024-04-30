import threading
import time
from functools import partial
from config import ERRORMESSAGE
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QProgressBar
from PyQt5.QtCore import QThread, pyqtSignal
from main_ui import Ui_MainWindow
from urllib.parse import unquote

import sys
import os
import subprocess

class SVNThread(QThread):

    output = pyqtSignal(str)
    processCount = pyqtSignal(int)
    progress = pyqtSignal(int)
    finish = pyqtSignal()
    def __init__(self, path, branch, isSwitch):
        super().__init__()
        self.path=path
        self.branch=branch
        self.isSwitch=isSwitch
        pass

    def run(self) -> None:
        if self.isSwitch:
            self.switch()
        else:
            self.check()
    def switch(self):

        self.traverseFolder(self.path, self.branch, True)


    def check(self):

        self.traverseFolder(self.path, self.branch)


    def getSvnRemoteUrl(self, data, branch, isSwitch):
        num = 0
        count = len(data)
        self.processCount.emit(count)
    # 获取文件的SVN信息
        for _, fileList in data.items():
            self.progress.emit(num)
            num += 1
            urlList = self.getUrlList(fileList)
            if not urlList:
                continue
            data1 = {}
            # print(fileList)
            # print(urlList)
            for file in fileList:
                for url in urlList:
                    filename = os.path.basename(url)
                    if file.endswith(filename):
                        data1[file] = url
            # print(data1)
            for filePath, url in data1.items():
                if isSwitch and branch not in url:
                    self.output.emit(filePath)
                    last = branch.split("/")[-1]
                    url = url.replace(url.split(last)[0]+last, branch)
                    cmd = f"svn switch \"{url}\" \"{filePath}\" --ignore-ancestry"
                    print(cmd)
                    # try:
                    r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         encoding="gbk")
                    stdout, stderr = r.communicate()
                    if stderr:
                        for e, message in ERRORMESSAGE.items():
                            stderr = stderr.replace(e, message)
                        decoded = unquote(stderr)
                        self.output.emit(f"ERROR:{decoded}")
                    # except:
                    #     self.output.emit(f"切换{filePath}失败，错误原因：{self.error}")
                    #     continue
                elif branch not in url:
                    self.output.emit(f"分支有误， 路径：{filePath} 分支：{url}\n")
        self.finish.emit()







    def getUrl(self, stdout):
        list = []
        for line in stdout.splitlines():
            if line.startswith('URL:'):
                remote_url = line.split(':', 1)[1].strip()
                decoded_url = unquote(remote_url)
                list.append(decoded_url)
        return list

    def getUrlList(self, fileList):
        allPath = ""
        for file in fileList:
            if "@" in file:
                file += "@"
            allPath += f"\"{file}\" "
        allPath = allPath.strip()
        command = f'svn info {allPath}'
        result = subprocess.Popen(command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding="gbk")
        stdout, stderr = result.communicate()
        urlList = []
        if not stderr:
            print(self.getUrl(stdout))
            urlList=self.getUrl(stdout)
        else:
            for file in fileList:
                if "@" in file:
                    file += "@"
                command = f'svn info \"{file}\"'

                result = subprocess.Popen(command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                                          encoding="gbk")
                stdout, stderr = result.communicate()
                if stderr:
                    continue
                urlList=self.getUrl(stdout)
        return urlList

    def traverseFolder(self, folder_path, branch, isSwitch=False):
        count = 30
        spiltNum = count
        data = {}
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                if ".svn" in file_path:
                    continue
                if count % spiltNum != 0:
                    data[count // spiltNum].append(file_path)
                else:
                    data[count // spiltNum] = [file_path]
                count += 1
        print(data)
        self.getSvnRemoteUrl(data, branch, isSwitch)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.path = ""
        self.branch = ""
        self.svnExe = os.path.join(os.path.dirname(__file__), "svn/svn.exe")
        self.maxcount =0

    def svn_thread(self,path, branch, isSwitch):
        self.thread = SVNThread(path, branch, isSwitch)


    def outPut(self,output):
        self.textEdit.append(output)
    def initUI(self):
        self.setupUi(self)
        self.show()
        self.chooseDirButton.clicked.connect(self.openFolder)
        self.dirPathLine.editingFinished.connect(self.onEditingFinished)
        self.svnUrlLine.editingFinished.connect(self.onEditingSvnLine)
        self.switchButton.clicked.connect(partial(self.startThread, True))
        self.checkButton.clicked.connect(partial(self.startThread, False))

    def setProcessMax(self,count):
        self.progress.setMaximum(count)
        self.maxcount=count
        # self.checkButton.clicked.connect(self.check)
    def setProgress(self,value):
        # self.textEdit.append(value)
        self.progress.setValue(value)

    def disabelButton(self):
        self.checkButton.setEnabled(False)
        self.switchButton.setEnabled(False)
        self.chooseDirButton.setEnabled(False)
    def enableButton(self):
        self.checkButton.setEnabled(True)
        self.switchButton.setEnabled(True)
        self.chooseDirButton.setEnabled(True)

    def finish(self):
        QMessageBox.information(self, "提示", "完成")
        self.enableButton()
        self.textEdit.append("进程结束")
        self.progress.setValue(self.maxcount)
    def startThread(self,isSwitch):

        self.path = self.dirPathLine.text()
        self.branch = self.svnUrlLine.text()
        if not os.path.exists(self.path):
            self.warning(f"请检查路径{self.path}是否正确")
            return
        if not self.branch:
            self.warning(f"SVN地址不能为空")
            return
        self.textEdit.clear()
        self.textEdit.append("进程开始")
        self.thread = SVNThread(self.path, self.branch, isSwitch)
        self.thread.output.connect(self.outPut)
        self.thread.processCount.connect(self.setProcessMax)
        self.thread.progress.connect(self.setProgress)
        self.thread.finish.connect(self.enableButton)
        self.thread.finish.connect(self.finish)
        self.checkButton.setEnabled(False)
        self.disabelButton()
        self.thread.start()
    def openFolder(self):
        self.path = QFileDialog.getExistingDirectory(None, "选择文件夹", "")
        self.dirPathLine.setText(self.path)

    def onEditingFinished(self):
        self.path = self.dirPathLine.text()
        self.textEdit.append(self.path)
        self.svn_thread(self.path, self.branch, True)


    def onEditingSvnLine(self):
        self.branch = self.svnUrlLine.text()



    def warning(self, msg):
        QMessageBox.warning(window, "错误", msg)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec_())
