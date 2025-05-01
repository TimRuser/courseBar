import rumps
import subprocess
import datetime
import json
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, file_to_watch, onChangeCallback):
        self.fileToWatch = os.path.abspath(file_to_watch)
        self.onChangeCallback = onChangeCallback

    def on_modified(self, event):
        if os.path.abspath(event.src_path) == self.fileToWatch:
            self.onChangeCallback()

class TimeUtilities():
    def isEntryToday(self, entry):
        weekday = datetime.datetime.today().weekday()
        if entry[1] == weekday:
            return True
        else:
            return False
 
    def isEntryCurrently(self, entry):
        timeNow = datetime.datetime.now()
        timeStart = datetime.datetime(timeNow.year,timeNow.month,timeNow.day,entry[2],entry[3])
        timeEnd = datetime.datetime(timeNow.year,timeNow.month,timeNow.day,entry[4],entry[5])

        if timeStart <= timeNow <= timeEnd:
            return True

    def isEntryNear(self, entry, nHours):
        timeNow = datetime.datetime.now()
        timeStart = datetime.datetime(timeNow.year,timeNow.month,timeNow.day,entry[2],entry[3])

        if datetime.timedelta(0) <=(timeStart - timeNow) <= datetime.timedelta(hours = nHours):
            if not self.isEntryCurrently(entry):
                return True 


class Timetable():
    def __init__(self, entries):
        self.entries = entries

    def getEntriesToday(self):
        weekday = datetime.datetime.today().weekday()
        entriesToday = []
        for entry in self.entries:
            if TimeUtilities().isEntryToday(entry):
                entriesToday.append(entry)

        return entriesToday
 
class Course():
    def __init__(self, id, name, shortName, entries, dir):
        self.id = id
        self.name = name
        self.shortName = shortName
        self.timeTable = Timetable(entries)
        self.dir = dir
           
    def returnEntriesToday(self):
        return self.timeTable.getEntriesToday()

class CourseApp(rumps.App):
    def __init__(self):
        super(CourseApp, self).__init__(name="Course")

        # Setting default values
        self.currentCourseId = "0"
        self.currentEntry = ()
        self.upcomingCourseId = "0"
        self.upcomingEntry = ()

        self.openedCourseId = "0"
        
        self.todaysCourses = {}

        # Loading configuration
        self.timeConfigWatcherEnabled = None
        self.configWatcher = None
        self.configPath = os.path.abspath('config.json')
        self.loadConfig() 

        # Menu Building
        self.currentCourseMenuItem = rumps.MenuItem("No current course", callback=None)
        self.upcomingCourseMenuItem = rumps.MenuItem("No upcoming course", callback=None)

        self.openCourseMenuItems = {
            "0": rumps.MenuItem(title="None", callback=self.selectingCourseToOpen),
        }

        self.menu = [
            self.currentCourseMenuItem,
            self.upcomingCourseMenuItem,
            "Open Course Notes",
            "Open Settings"
        ]

        # Today's data
        self.todaysDate = datetime.datetime.today() - datetime.timedelta(days = 1)

        self.menu["Open Course Notes"].add(self.openCourseMenuItems["0"])
        for course in self.courseList:
            item = rumps.MenuItem(title=self.courseList[course].name, callback=self.selectingCourseToOpen)
            self.menu["Open Course Notes"].add(item)
            self.openCourseMenuItems[course] = item

        self.selectingCourseToOpen(None)
        

        # Opening settings window
        @rumps.clicked("Open Settings")
        def openSettings(sender):
            print("Opening settings")
            # Open default editor for .json
            subprocess.call(('open', self.configPath))

            # Start watchdog for config.json file
            if self.configWatcher != None:
                self.configWatcher.stop()
                self.configWatcher.join()
            event_handler = ConfigFileHandler(self.configPath, self.loadConfig)
            observer = Observer()
            observer.schedule(event_handler, path=os.path.dirname(self.configPath), recursive=False)
            observer.start()

            self.timeConfigWatcherEnabled = datetime.datetime.now()
            self.configWatcher = observer

            print("Started config watchdog")

        @rumps.timer(1200)
        def checkWatcher(sender):
            # Check if watchdog is active and deactivate it if it has been active more than 20 minutes since start
            if self.configWatcher != None:
                if (datetime.datetime.now() - self.timeConfigWatcherEnabled) >= datetime.timedelta(minutes=20):
                    self.configWatcher.stop()
                    self.configWatcher.join()
                    self.configWatcher = None
                    self.timeConfigWatcherEnabled = None
                    print("Deactivated config watchdog")

        # Checking for courses if the day changed
        @rumps.timer(120)
        def checkIfCoursesFromToday(sender):
            if self.todaysDate.day != datetime.datetime.today().day:
                self.updateTodaysCourses()    
                self.todaysDate = datetime.datetime.today()
            print("Performed up-to-date check")

        @rumps.timer(30)
        def callCheckCourses(sender):
            self.updateCurrentCourses()


    def loadConfig(self):
        with open(self.configPath, 'r') as f:
            config = json.load(f)        

        self.noCourseTitle = config['defaultTitle']
        self.title = self.noCourseTitle
        self.hIsNear = config['hoursIsNear']

        # Load courses
        self.courseList = {}
        for i in range(1,len(config['Courses']) + 1):
            course = config['Courses'][i-1]
            self.courseList[str(i)] = Course(i, course['name'], course['shortName'],course['entries'],course['directory'])

        print("Config was loaded")

        if len(self.todaysCourses) > 0:
            self.updateTodaysCourses()
            self.updateCurrentCourses()
        
    def watchConfigFile(configPath, callback):
        event_handler = ConfigFileHandler(configPath, callback)
        observer = Observer()
        observer.schedule(event_handler, path=os.path.dirname(configPath), recursive=False)
        observer.start()
        return observer

    def updateTodaysCourses(self):
        for course in self.courseList:
            courseEntriesToday = self.courseList[course].returnEntriesToday()
            if len(courseEntriesToday) > 0:
                self.todaysCourses[course] = courseEntriesToday
        print("Updated today's courses") 


    def updateCurrentCourses(self):
        # Checking for current courses
        for course in self.todaysCourses:
            for entry in self.todaysCourses[course]:
                if TimeUtilities().isEntryCurrently(entry):
                    self.currentCourseId = course
                    self.currentEntry = entry
                    break
            if self.currentCourseId == course:
                break
        
        # Checking for upcoming courses
        for course in self.todaysCourses:
            for entry in self.todaysCourses[course]:
                if TimeUtilities().isEntryNear(entry,self.hIsNear):
                    self.upcomingCourseId = course
                    self.upcomingEntry = entry
                    break
            if self.upcomingCourseId == course:
                break

        # Setting the menu
        if self.currentCourseId == "0":
            if self.upcomingCourseId != "0":
                self.title = self.courseList[self.upcomingCourseId].shortName + " at " + str(self.upcomingEntry[4]) + ":" + (str(self.upcomingEntry[5]) if self.upcomingEntry[5] > 9 else ("0" + str(self.upcomingEntry[5]))) + " in " + self.upcomingEntry[0]
                self.currentCourseMenuItem = "No current course"
                self.upcomingCourseMenuItem.title = "Soon: " + self.courseList[self.upcomingCourseId].name + " at " + str(self.upcomingEntry[4]) + ":" + (str(self.upcomingEntry[5]) if self.upcomingEntry[5] > 9 else ("0" + str(self.upcomingEntry[5])))
        else:
            self.title = self.courseList[self.currentCourseId].shortName + " until " + str(self.currentEntry[4]) + ":" + (str(self.currentEntry[5]) if self.currentEntry[5] > 9 else ("0" + str(self.currentEntry[5]))) + " in " + self.currentEntry[0]
            self.currentCourseMenuItem.title = "Now: " + self.courseList[self.currentCourseId].name
            if self.upcomingCourseId != "0":
                self.upcomingCourseMenuItem.title = "Soon: " + self.courseList[self.upcomingCourseId].name + " at " + str(self.upcomingEntry[4]) + ":" + (str(self.upcomingEntry[5]) if self.upcomingEntry[5] > 9 else ("0" + str(self.upcomingEntry[5])))
            
        print("Checked current and upcoming courses")

    def openCourse(self, courseId):
        command = 'cd ~/Documents/Notizen/' + self.courseList[courseId].dir + ' && vim main.tex'
        apple_script = f'''
        tell application "iTerm"
            create window with default profile
            tell current session of current window
                write text "{command}"
                delay 1
                write text ":VimtexCompile"
            end tell
        end tell
        '''
        subprocess.run(["osascript", "-e", apple_script])

    def closeCourse(self):
        script = 'tell application "iTerm" to close current window'
        subprocess.run(["osascript", "-e", script])

        script = 'tell application "Skim" to close every window'
        subprocess.run(["osascript", "-e", script])

    def selectingCourseToOpen(self, sender):
        if sender == None or sender.title == "None":
            self.openingCourse("0")
        else:
            for i in range(1,len(self.courseList)):
                if sender.title == self.courseList[str(i)].name:
                    courseId = str(i)
                    self.openingCourse(courseId)
                    break

    def openingCourse(self, courseId):
        if int(self.openedCourseId) > 0:
            self.closeCourse()
        if int(courseId) > 0:
            self.openCourse(courseId)
        self.openedCourseId = courseId
        if courseId != "0":
            for name, item in self.openCourseMenuItems.items():
                item.state = int(name == courseId)
        else:
            for name, item in self.openCourseMenuItems.items():
                item.state = False
            self.openCourseMenuItems["0"].state = True


if __name__ == '__main__':
    CourseApp().run()
