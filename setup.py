import rumps
import subprocess
import datetime

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
            return True 


class Timetable():
    def __init__(self, entries):
        self.entries = [("A401",2,19,00,20,00), ("A302",2,21,20,22,20), ("A202",3,10,30,11,15)]

    def getEntriesToday(self):
        weekday = datetime.datetime.today().weekday()
        entriesToday = []
        for entry in self.entries:
            if TimeUtilities().isEntryToday(entry):
                entriesToday.append(entry)

        return entriesToday
 
class Course():
    def __init__(self, id, name, shortName, entries):
        self.id = id
        self.name = name
        self.shortName = shortName
        self.timeTable = Timetable(entries)
        self.dir = 'Test'
           
    def returnEntriesToday(self):
        return self.timeTable.getEntriesToday()

class CourseApp(rumps.App):
    def __init__(self):
        super(CourseApp, self).__init__(name="Course")

        # Set default course
        self.noCourseTitle = "No current course"
        self.title = self.noCourseTitle

        # List of all courses
        self.courseList = {
            "1": Course(1, 'Mathe','M',()),
            "2": Course(2, 'Deutsch', 'de',())
        }
        self.openCourseMenuItems = {
            "0": rumps.MenuItem(title="None", callback=self.selectingCourseToOpen),
        }

        # Current course
        self.currentCourseId = "0"
        self.currentEntry = ()
        # Upcoming course
        self.upcomingCourseId = "0"
        self.upcomingEntry = ()

        # Opened course
        self.openedCourseId = "0"

        # Menu Building
        self.currentCourseMenuItem = rumps.MenuItem("No current course", callback=None)
        self.upcomingCourseMenuItem = rumps.MenuItem("No upcoming course", callback=None)
        self.menu = [
            self.currentCourseMenuItem,
            self.upcomingCourseMenuItem,
            "Open Course Notes"
        ]

        # Today's data
        self.todaysDate = datetime.datetime.today() - datetime.timedelta(days = 1)
        self.todaysCourses = {}

        self.menu["Open Course Notes"].add(self.openCourseMenuItems["0"])
        for course in self.courseList:
            item = rumps.MenuItem(title=self.courseList[course].name, callback=self.selectingCourseToOpen)
            self.menu["Open Course Notes"].add(item)
            self.openCourseMenuItems[course] = item

        self.selectingCourseToOpen("None", True)
        
        # Checking for courses if the day changed
        @rumps.timer(60)
        def timerCheck(sender):
            if self.todaysDate.day != datetime.datetime.today().day:
                for course in self.courseList:
                    courseEntriesToday = self.courseList[course].returnEntriesToday()
                    if len(courseEntriesToday) > 0:
                        self.todaysCourses[course] = courseEntriesToday
                print("Updated today's courses") 
                self.todaysDate = datetime.datetime.today()
            print("Performed up-to-date check")

        # Updating current and upcoming courses
        @rumps.timer(10)
        def getCurrentCourse(sender):
            # Checking for current courses
            for course in self.todaysCourses:
                for entry in self.todaysCourses[course]:
                    if TimeUtilities().isEntryCurrently(entry):
                        self.currentCourseId = course
                        self.currentEntry = entry
                        break
                if self.currentCourseId == course:
                    print("Updated current course")
                    break
            
            # Checking for upcoming courses
            for course in self.todaysCourses:
                for entry in self.todaysCourses[course]:
                    if TimeUtilities().isEntryNear(entry,2):
                        self.upcomingCourseId = course
                        self.upcomingEntry = entry
                        break
                if self.upcomingCourseId == course:
                    print("Updated upcoming course")
                    break

            # Setting the menu
            if self.currentCourseId == "0":
                if self.upcomingCourseId != "0":
                    self.title = self.courseList[self.upcomingCourseId].shortName + " at " + str(self.upcomingEntry[4]) + ":" + (str(self.upcomingEntry[5]) if self.upcomingEntry[5] > 9 else ("0" + str(self.upcomingEntry[5]))) + " in " + self.upcomingEntry[0]
                    self.currentCourseMenuItem = "No current course"
                    self.upcomingCourseMenuItem.title = "Soon: " + self.courseList[self.upcomingCourseId].name
            else:
                self.title = self.courseList[self.currentCourseId].shortName + " until " + str(self.currentEntry[4]) + ":" + (str(self.currentEntry[5]) if self.currentEntry[5] > 9 else ("0" + str(self.currentEntry[5]))) + " in " + self.upcomingEntry[0]
                self.currentCourseMenuItem.title = "Now: " + self.courseList[self.currentCourseId].name
                if self.upcomingCourseId != "0":
                    self.upcomingCourseMenuItem.title = "Soon: " + self.courseList[self.upcomingCourseId].name
                

            print("Performed course check")

    def openCourse(self, courseId):
        command = 'cd ~/Documents/Notizen/' + self.courseList[courseId].dir + ' && vim test.tex'
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

    def selectingCourseToOpen(self, sender, reset=False):
        if reset:
            self.openingCourse("0")
        else:
            for i in range(len(self.courseList)):
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
        for name, item in self.openCourseMenuItems.items():
            item.state = int(name == courseId)


if __name__ == '__main__':
    CourseApp().run()
