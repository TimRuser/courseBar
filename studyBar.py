import rumps
import subprocess
import datetime
import math
import json
import os
import re
from pathlib import Path
import webbrowser
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from TexSoup import TexSoup, TexNode

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

    def getTimeLeft(self, entry):
        timeNow = datetime.datetime.now()
        timeEnd = datetime.datetime(timeNow.year,timeNow.month,timeNow.day,entry[4],entry[5])

        return timeEnd - timeNow

    def getEarlierEntry(self,entry1,entry2):
        if entry1 == None:
            return entry2
        elif entry2 == None:
            return entry1

        timeNow = datetime.datetime.now()
        timeStart1 = datetime.datetime(timeNow.year,timeNow.month,timeNow.day,entry1[2],entry1[3])
        timeStart2 = datetime.datetime(timeNow.year,timeNow.month,timeNow.day,entry2[2],entry2[3])

        if (timeStart1 - timeStart2) <= datetime.timedelta(0):
            return entry1
        else:
            return entry2
        

    def convertMinutesToHourMinutes(self, minutes):
        hours = math.floor(minutes / 60)
        minutes = minutes - (hours * 60)
        return hours, minutes


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

        self.todaysCourses = {}

        self.lessonFilePattern = re.compile(r'^les_\d{2}\.tex$')

        # Loading configuration
        self.configPath = os.path.abspath('config.json')
        print("Config path set to ", self.configPath)
        self.loadConfig(initial=True) 

        # Starting configuration watchdog
        eventHandler = ConfigFileHandler(self.configPath, self.loadConfig)
        observer = Observer()
        observer.schedule(eventHandler, path=os.path.dirname(self.configPath), recursive=False)
        observer.start()

        self.configWatcher = observer

        print("Started config watchdog")

        # Menu Building
        self.currentCourseMenuItem = rumps.MenuItem(self.noCurrentCourseTitle, callback=None)
        self.upcomingCourseMenuItem = rumps.MenuItem(self.noUpcomingCourseTitle, callback=None)

        self.openCourseMenuItems = {}
        self.createLectureNoteItems = {}

        self.makeMenu()

        # Today's date
        self.todaysDate = datetime.datetime.today() - datetime.timedelta(days = 1)

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


    def loadConfig(self, initial=False):
        with open(self.configPath, 'r', encoding='utf-8') as f:
            config = json.load(f)        

        self.noCurrentCourseTitle = config['defaultCurrentTitle']
        self.noUpcomingCourseTitle = config['defaultUpcomingTitle']
        self.title = self.noCurrentCourseTitle
        self.hIsNear = config['hoursIsNear']
        self.notesPath = config['notesPath']

        # Load courses
        self.courseList = {}
        for i in range(1,len(config['Courses']) + 1):
            course = config['Courses'][i-1]
            self.courseList[str(i)] = Course(i, course['name'], course['shortName'],course['entries'],course['directory'])

        print("Config was loaded")

        if not initial:
            self.updateTodaysCourses()
            if len(self.todaysCourses) > 0:
                self.updateCurrentCourses()
            else:
                self.currentCourseMenuItem.title = self.noCurrentCourseTitle
                self.upcomingCourseMenuItem.title = self.noUpcomingCourseTitle
        
    # Functions for updating course display
    def updateTodaysCourses(self):
        self.todaysCourses = {}
        for course in self.courseList:
            courseEntriesToday = self.courseList[course].returnEntriesToday()
            if len(courseEntriesToday) > 0:
                self.todaysCourses[course] = courseEntriesToday
        print("Updated today's courses") 

    def updateCurrentCourses(self):
        # Checking for current courses
        self.currentCourseId = "0"
        for course in self.todaysCourses:
            for entry in self.todaysCourses[course]:
                if TimeUtilities().isEntryCurrently(entry):
                    self.currentCourseId = course
                    self.currentEntry = entry
                    break
            if self.currentCourseId == course:
                break
        
        # Checking for upcoming courses
        self.upcomingCourseId = "0"
        soonestCourseId = "0"
        soonestEntry = None
        for course in self.todaysCourses:
            for entry in self.todaysCourses[course]:
                if TimeUtilities().isEntryNear(entry,self.hIsNear):
                    if TimeUtilities().getEarlierEntry(entry,soonestEntry) == entry:
                        soonestEntry = entry
                        soonestCourseId = course
                    break
        self.upcomingCourseId = soonestCourseId
        self.upcomingEntry = soonestEntry

        # Setting the menu
        if self.currentCourseId == "0":
            self.currentCourseMenuItem.title = self.noCurrentCourseTitle
            if self.upcomingCourseId != "0":
                self.title = self.courseList[self.upcomingCourseId].shortName + " at " + str(self.upcomingEntry[2]) + ":" + (str(self.upcomingEntry[3]) if self.upcomingEntry[3] > 9 else ("0" + str(self.upcomingEntry[3]))) + " in " + self.upcomingEntry[0]
            else:
                self.title = self.noCurrentCourseTitle
        else:
            self.title = self.courseList[self.currentCourseId].shortName + " until " + str(self.currentEntry[4]) + ":" + (str(self.currentEntry[5]) if self.currentEntry[5] > 9 else ("0" + str(self.currentEntry[5]))) + " in " + self.currentEntry[0]
            hoursLeft, minutesLeft = TimeUtilities().convertMinutesToHourMinutes(round(TimeUtilities().getTimeLeft(self.currentEntry).seconds / 60))
            if hoursLeft > 0:
                self.currentCourseMenuItem.title = str(hoursLeft) + ":" + (str(minutesLeft) if minutesLeft > 9 else ("0" + str(minutesLeft))) + "h left of " + self.courseList[self.currentCourseId].name
            else:
                self.currentCourseMenuItem.title = str(minutesLeft) + "min left of " + self.courseList[self.currentCourseId].name

        if self.upcomingCourseId != "0":
            self.upcomingCourseMenuItem.title = self.courseList[self.upcomingCourseId].name + " at " + str(self.upcomingEntry[2]) + ":" + (str(self.upcomingEntry[3]) if self.upcomingEntry[3] > 9 else ("0" + str(self.upcomingEntry[3]))) + " in " + self.upcomingEntry[0]
        else:
            self.upcomingCourseMenuItem.title = self.noUpcomingCourseTitle
        
        # Add files to current course menu
        if self.currentCourseId != "0":
            directory = Path(os.path.join(self.notesPath, self.courseList[self.currentCourseId].dir)).expanduser()
            openCourseNotes = rumps.MenuItem("Open Course Note")
            newLectureNote = rumps.MenuItem("New Lecture Note", callback=self.currentWrapperCreateLectureNote)
            for file in [f.name for f in directory.iterdir() if f.is_file() and f.suffix == '.tex']:
                openCourseNotes.add(rumps.MenuItem(title=file, callback=self.currentWrapperOpenCourseNotes))
            self.currentCourseMenuItem.add(openCourseNotes)
            self.currentCourseMenuItem.add(newLectureNote)
        else:
            if len(self.currentCourseMenuItem.items()) > 0:
                self.currentCourseMenuItem.clear()

        # Add files to upcoming course menu
        if self.upcomingCourseId != "0":
            directory = Path(os.path.join(self.notesPath, self.courseList[self.upcomingCourseId].dir)).expanduser()
            openCourseNotes = rumps.MenuItem("Open Course Note")
            newLectureNote = rumps.MenuItem("New Lecture Note", callback=self.upcomingWrapperCreateLectureNote)
            for file in [f.name for f in directory.iterdir() if f.is_file() and f.suffix == '.tex']:
                openCourseNotes.add(rumps.MenuItem(title=file, callback=self.upcomingWrapperOpenCourseNotes))
            self.upcomingCourseMenuItem.add(openCourseNotes)
            self.upcomingCourseMenuItem.add(newLectureNote)
        else:
            if len(self.upcomingCourseMenuItem.items()) > 0:
                self.upcomingCourseMenuItem.clear()

        self.makeMenu()
        print("Checked current and upcoming courses")

    def makeMenu(self):
        if self.menu != None:
            self.menu.clear()

        self.menu = [
            self.currentCourseMenuItem,
            self.upcomingCourseMenuItem,
            rumps.separator,
            "Open Course Notes",
            "New Lecture Note",
            rumps.separator,
            rumps.MenuItem("Show timetable", callback=self.openTimetable),
            rumps.MenuItem("Open Settings", callback=self.openSettings),
        ]
        # Adding open course notes options
        for course in self.courseList:
            item = rumps.MenuItem(title=self.courseList[course].name, callback=self.openCourseNotes)
            self.menu["Open Course Notes"].add(item)
            self.openCourseMenuItems[course] = item
        # Adding create lecture note options
        for course in self.courseList:
            item = rumps.MenuItem(title=self.courseList[course].name, callback=self.createLectureNote)
            self.menu["New Lecture Note"].add(item)
            self.createLectureNoteItems[course] = item
        
    # Open course note functions
    def currentWrapperOpenCourseNotes(self, sender):
        self.openCourseNotes(None, self.currentCourseId, sender.title)

    def upcomingWrapperOpenCourseNotes(self, sender):
        self.openCourseNotes(None, self.upcomingCourseId, sender.title)

    def openCourseNotes(self, sender, courseId = None, fileName = None):
        if courseId == None:
            for i in range(1,len(self.courseList)):
                if sender.title == self.courseList[str(i)].name:
                    courseId = str(i)
                    break
        if fileName == None:
            self.openingCourseNote(courseId)
        else:
            self.openingCourseNote(courseId, fileName)

    def openingCourseNote(self, courseId, fileName = None):
        if fileName == None:
            command = 'cd ' + os.path.join(self.notesPath, self.courseList[courseId].dir)
            apple_script = f'''
            tell application "iTerm"
                create window with default profile
                tell current session of current window
                    write text "{command}"
                end tell
            end tell
            '''
        else:
            command = 'cd ' + os.path.join(self.notesPath, self.courseList[courseId].dir) + ' && vim ' + fileName
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

    # New lecture note functions
    def currentWrapperCreateLectureNote(self, sender):
        self.createLectureNote(None, self.currentCourseId)

    def upcomingWrapperCreateLectureNote(self, sender):
        self.createLectureNote(None, self.upcomingCourseId)

    def createLectureNote(self, sender, courseId = None):
        if courseId == None:
            for i in range(1,len(self.courseList)):
                    if sender.title == self.courseList[str(i)].name:
                        courseId = str(i)
                        break
        directory = Path(os.path.join(self.notesPath, self.courseList[courseId].dir)).expanduser()
        files = [f.name for f in directory.iterdir() if f.is_file() and f.suffix == '.tex']
        numbers = []
        for file in files:
            numbers += re.findall(r'\d+', file)
        if len(numbers) > 0:
            numbers.sort()
            num = int(numbers[-1]) + 1
        else:
            num = 1
        fileName = "les_" + str(num) + ".tex"
        self.openingCourseNote(courseId, fileName)

        # Add input to master.tex if exists
        commentMarker = "% end lessons"
        if 'master.tex' in files:
            masterTexPath = directory.joinpath("master.tex")
            with open(masterTexPath, 'r') as f:
                lines = f.readlines()

            modified_lines = []
            lineToAdd = "\input{" + fileName + "}" + "\n"

            # Check if not already in file
            if len([line for line in lines if lineToAdd in line]) == 0:
                for line in lines:
                    if commentMarker in line:
                        modified_lines.append(lineToAdd)
                    modified_lines.append(line)

                # Write the modified file
                with open(masterTexPath, 'w') as f:
                    f.writelines(modified_lines)


    # Opening timetable 
    def openTimetable(self, sender):
        if os.path.isfile('timetable.pdf'):
            print("Opening timetable")
            # Open pdf in the browser
            webbrowser.open_new(r'file://' + os.path.abspath('timetable.pdf'))

    # Opening config
    def openSettings(self, sender):
        print("Opening settings")
        # Open default editor for .json
        subprocess.call(('open', self.configPath))

        # Open finder to folder
        subprocess.call(["open", "-R", 'timetable.pdf'])



if __name__ == '__main__':
    CourseApp().run()
