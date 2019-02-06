import cmd
from sqlite3 import connect, Connection, Cursor
from datetime import datetime
from time import time
from typing import Callable, Tuple, List
from re import split, escape
from re import compile as regex_compile


connection: Connection = connect("rqdatabase.db")
cursor: Cursor = connection.cursor()
dosql: Callable[[str, Tuple], None] = cursor.execute
commit: Callable[[], None] = connection.commit


def is_substring(test: str, case: str, offset: int=0) -> bool:
    return test in tuple(
        case[0:offset + 1 + i]
        for i in range(
            len(case) - offset
        )
    )


def show_all_names():
    dosql("SELECT name FROM requests WHERE completed=0")
    names_displayed = 0
    for name in cursor.fetchall():
        names_displayed += 1
        print("  >", str(name[0]).title())

    if names_displayed < 1:
        print("  > No current feature requests.")


class RequestShell(cmd.Cmd):
    prompt = ">>> "
    break_char = r"\n"

    def __init__(self):
        super().__init__()

        # create the requests table
        dosql("""
        CREATE TABLE IF NOT EXISTS requests
        (
          unix INTEGER,
          name TEXT,
          description TEXT,
          completed INTEGER
        )
        """)

    def preloop(self):
        print("CURRENT FEATURE REQUESTS:")
        show_all_names()
        print()

    # def postloop(self):
    #     self.close()

    def emptyline(self):
        pass

    def do_new(self, arg):
        """Submit a new request. The only argument is the name of the request."""
        if len(arg) < 1:
            print("Enter a short, descriptive name for the new request:")
            name = input(self.prompt).lower()
        else:
            name = arg.lower()
        print("Enter a description for the request.", end=" ")
        desc = self.enter_text()
        unix = time()
        dosql("""
        INSERT INTO requests (unix, name, description, completed)
        VALUES (?, ?, ?, 0)
        """, (unix, name, desc))
        commit()
        print("Request added to database.")

    def do_edit(self, arg):
        """Edit an aspect of the given request."""
        req = self.search_for_request(arg)
        if len(req) > 0:
            print("Enter the number of the part of the request you wish to edit:")
            print(" 1) Name")
            print(" 2) Description")
            while True:
                try:
                    choice = int(input(self.prompt))
                    assert choice in (1, 2)
                    break
                except (ValueError, AssertionError):
                    continue

            if not self.ask_yes_no():
                return

            if choice == 1:
                new_name = input(f"[{req.title()}] {self.prompt}").lower()
                dosql("""
                UPDATE requests SET name=? WHERE name=? AND completed=0
                """, (new_name, req))
                commit()

                print("Request name updated.")

            elif choice == 2:
                dosql("""
                SELECT description FROM requests WHERE name=? AND completed=0
                """, (req, ))
                treq = cursor.fetchone()
                desc_parts = tuple(split(escape(self.break_char), treq[0]))
                new_desc = self.enter_text(desc_parts)

                dosql("""
                UPDATE requests SET description=? WHERE name=? AND completed=0
                """, (new_desc, req))
                commit()

                print("Request description updated.")
        else:
            print("No request found by that name.")

    def search_for_request(self, unfin: str) -> str:
        """Return a completed request name."""
        search_reg = regex_compile(escape(unfin.lower()))
        dosql("SELECT name FROM requests WHERE completed=0")
        returns: List[str] = []
        for row in cursor.fetchall():
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
        dosql("SELECT * FROM requests WHERE name=? AND completed=0", (name,))
        for row in cursor.fetchall():
            print(
                str(row[1]).title(), "-",
                datetime.fromtimestamp(row[0]).strftime(
                    "Requested on %m/%d/%Y at %I:%M%p"
                )
            )
            print("\n".join(split(escape(self.break_char), row[2])), "\n")

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
        """Show request information."""
        req = self.search_for_request(arg)
        if len(req) > 0:
            self.show_request(req)
        else:
            print("No request found by that name.")

    def do_complete(self, arg):
        """Mark the given request as completed."""
        req = self.search_for_request(arg)
        if len(req) > 0:
            print("This will mark the following request as completed:")
            print("  >", req.title())
            if not self.ask_yes_no():
                return
            dosql("""
            UPDATE requests SET completed=1 WHERE name=? AND completed=0
            """, (req,))
            commit()
        else:
            print("No request found by that name.")

    def do_delete(self, arg):
        """Delete the given request."""
        req = self.search_for_request(arg)
        if len(req) > 0:
            print("This will delete the following request:")
            print("  >", req.title())
            if not self.ask_yes_no():
                return
            dosql("""
            DELETE FROM requests WHERE name=?
            """, (req, ))
        else:
            print("No request found by that name.")

    def do_show(self, arg):
        """Show all current requests."""
        print("CURRENT FEATURES REQUESTS:")
        show_all_names()
        print()

    def do_quit(self, arg):
        """Quit the interpreter with code <arg>."""
        # self.close()
        try:
            quit(int(arg))
        except ValueError:
            quit(0)

    def do_exit(self, arg):
        """Exit the interpreter with code <arg>"""
        self.do_quit(arg)

    def close(self):
        cursor.close()
        connection.close()


if __name__ == '__main__':
    RSI = RequestShell()
    try:
        RSI.cmdloop()
    except SystemExit:
        RSI.close()
