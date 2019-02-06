import cmd
from sqlite3 import connect, Connection, Cursor
from datetime import datetime
from time import time
from typing import Callable, Tuple, List
from re import split, escape
from re import compile as regex_compile


def is_substring(test: str, case: str, offset: int=0) -> bool:
    return test in tuple(
        case[0:offset + 1 + i]
        for i in range(
            len(case) - offset
        )
    )


class RequestShell(cmd.Cmd):
    prompt = ">>> "
    break_char = r"\n"

    def __init__(self, file="rqdatabase.db"):
        super().__init__()

        # ****** Argument Attributes ******
        self._file = file

        # ****** Connection Information ******
        self.connection: Connection = connect(file)
        """SQLite operates in system memory rather than on a server.
        Therefore, instead of connecting to a server, we connect to
        the file that the database will be stored in."""
        self.cursor: Cursor = self.connection.cursor()

        # ****** Method Shorthands ******
        self.post_sql: Callable[[str, Tuple], None] = self.cursor.execute
        self.commit_sql: Callable[[], None] = self.connection.commit

        # ****** Request Table Creation ******
        self.post_sql("""
        CREATE TABLE IF NOT EXISTS requests
        (
          unix INTEGER,
          name TEXT,
          description TEXT,
          completed INTEGER
        )
        """)

    @property
    def file(self):
        """The file attribute should only be accessed, not changed."""
        return self._file

    def preloop(self):
        print("CURRENT FEATURE REQUESTS:")
        self.show_all_names()
        print()

    def postloop(self):
        self.close()

    def emptyline(self):
        pass

    def do_new(self, arg):
        """Submit a new request. Usage: new <requesst_name|fragment>"""
        # If the user does not enter a name with the command, prompt them for one.
        if len(arg) < 1:
            print("Enter a short, descriptive name for the new request:")
            name = input(self.prompt).lower()
        else:
            name = arg.lower()

        print("Enter a description for the request.", end=" ")

        # ****** Enter Text Editor ******
        desc = self.enter_text()

        # ****** Commit Request to Database ******
        unix = time()
        self.post_sql("""
        INSERT INTO requests (unix, name, description, completed)
        VALUES (?, ?, ?, 0)
        """, (unix, name, desc))
        self.commit_sql()

        print("Request added to database.")

    def do_edit(self, arg):
        """Edit an aspect of the given request. Usage: edit <request_name|fragment>"""
        # Ensure user enters something
        if len(arg) < 1:
            print("Usage: edit <request_name|fragment>")
            self.show_all_names()
            return False

        # Search database for requests containing the substring arg
        req = self.search_for_request(arg)
        if len(req) == 0:
            print("No request found by that name.")
            return False

        # ****** Edit Choice ******
        print("Enter the number of the part of the request you wish to edit:")
        print(" 1) Name")
        print(" 2) Description")
        while True:
            try:
                choice = int(input(self.prompt)) - 1
                assert choice in (0, 1)
                break
            except (ValueError, AssertionError):
                continue

        if not self.ask_yes_no():
            return False

        if not choice:
            new_name = input(f"[{req.title()}] {self.prompt}").lower()
            self.post_sql("""
            UPDATE requests SET name=? WHERE name=? AND completed=0
            """, (new_name, req))
            self.commit_sql()

            print("Request name updated.")
            return False

        else:
            # get request information
            self.post_sql("""
            SELECT description FROM requests WHERE name=? AND completed=0
            """, (req, ))
            treq = self.cursor.fetchone()
            desc_parts = tuple(split(escape(self.break_char), treq[0]))
            new_desc = self.enter_text(desc_parts)

            self.post_sql("""
            UPDATE requests SET description=? WHERE name=? AND completed=0
            """, (new_desc, req))
            self.commit_sql()

            print("Request description updated.")
            return False

    def search_for_request(self, unfin: str) -> str:
        """Return a completed request name."""
        search_reg = regex_compile(escape(unfin.lower()))
        self.post_sql("SELECT name FROM requests WHERE completed=0")
        returns: List[str] = []
        for row in self.cursor.fetchall():
            req = search_reg.search(row[0])
            if req is not None:
                returns.append(row[0])

        if len(returns) < 1:
            return ""

        elif len(returns) > 1:
            print("Possible requests:")
            for index, item in enumerate(returns):
                print(f" {index + 1})", item.title())

            print("Please enter the number of the desired request:")
            while True:
                try:
                    x = int(input(self.prompt)) % len(returns)
                except ValueError:
                    continue

                try:
                    return returns[x - 1]
                except IndexError:
                    continue

        else:
            return returns[0]

    def show_request(self, name):
        name = name.lower()
        self.post_sql("SELECT * FROM requests WHERE name=? AND completed=0", (name,))
        for row in self.cursor.fetchall():
            print(
                str(row[1]).title(), "-",
                datetime.fromtimestamp(row[0]).strftime(
                    "Requested on %m/%d/%Y at %I:%M%p"
                )
            )
            print("\n".join(split(escape(self.break_char), row[2])), "\n")

    def show_all_names(self):
        self.post_sql("SELECT name FROM requests WHERE completed=0")

        print("CURRENT FEATURES REQUESTS:")
        names_displayed = 0
        for name in self.cursor.fetchall():
            names_displayed += 1
            print("  >", str(name[0]).title())

        if names_displayed < 1:
            print("  > No current feature requests.\n")

    def ask_yes_no(self) -> bool:
        print("Are you sure you want to continue? (y/n)")
        while True:
            try:
                x = input(self.prompt).lower()
                assert x in ("yes", "no", "y", "n")
            except AssertionError:
                continue
            if x in ("yes", "y"):
                return True
            else:
                return False

    def enter_text(self, prev_text: Tuple[str, ...] = ()) -> str:
        """Multi-line text-entry."""
        print("Type 'EOD' when finished.\nType '<<' to keep original line.\nPress return to enter a newline.")
        index = 0
        text: List[str] = []
        while True:
            if (index + 1) > len(prev_text):
                prompt = self.prompt
            else:
                prompt = f"[{prev_text[index]}]{self.prompt}"
            x = input(prompt)
            if x[-3:] == "EOD":
                if x[:-3] != "":
                    text.append(x[:-3])
                break
            if x == "<<":
                x = prev_text[index]
            text.append(x)
            index += 1
        return self.break_char.join(text)

    def do_expand(self, arg):
        """Show request information. Usage: expand <request_name|fragment>"""
        req = self.search_for_request(arg)
        if len(req) > 0:
            self.show_request(req)
        else:
            print("No request found by that name.")

    def do_complete(self, arg):
        """Mark the given request as completed. Usage: complete <request_name|fragment>"""
        req = self.search_for_request(arg)
        if len(req) > 0:
            print("This will mark the following request as completed:")
            print("  >", req.title())
            if not self.ask_yes_no():
                return
            self.post_sql("""
            UPDATE requests SET completed=1 WHERE name=? AND completed=0
            """, (req,))
            self.commit_sql()
        else:
            print("No request found by that name.")

    def do_delete(self, arg):
        """Delete the given request. Usage: delete <request_name|fragment>"""
        req = self.search_for_request(arg)
        if len(req) > 0:
            print("This will delete the following request:")
            print("  >", req.title())
            if not self.ask_yes_no():
                return
            self.post_sql("""
            DELETE FROM requests WHERE name=?
            """, (req, ))
        else:
            print("No request found by that name.")

    def do_show(self, arg):
        """Show all current requests. Usage: show"""
        self.show_all_names()

    def do_quit(self, arg):
        """Quit the interpreter with code <arg>. Usage: quit <code>"""
        return True

    def do_exit(self, arg):
        """Exit the interpreter with code <arg>. Usage: exit <code>"""
        self.do_quit(arg)

    def close(self):
        self.cursor.close()
        self.connection.close()


if __name__ == '__main__':
    RSI = RequestShell()
    try:
        RSI.cmdloop()
    except SystemExit:
        RSI.close()
