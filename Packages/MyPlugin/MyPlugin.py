import sublime
import sublime_plugin


class hahaCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.insert(edit, 0, "haha")
