"""테스트용 메모리 기반 Sheets API 대역. 이 프로젝트가 쓰는 호출만 흉내낸다."""
import re


class _Call:
    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


def _parse_a1(a1):
    m = re.fullmatch(r"'((?:[^']|'')+)'!([A-Z]+)(\d*)(?::([A-Z]+)(\d*))?", a1)
    title = m.group(1).replace("''", "'")
    col = lambda s: sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed(s))) - 1
    c0 = col(m.group(2))
    r0 = int(m.group(3)) - 1 if m.group(3) else 0
    c1 = col(m.group(4)) if m.group(4) else c0
    r1 = int(m.group(5)) - 1 if m.group(5) else None
    return title, r0, r1, c0, c1


class FakeSheets:
    def __init__(self):
        self.sheets = {}  # title -> {"id": int, "rows": list[list]}
        self.requests = []

    # service.spreadsheets()
    def spreadsheets(self):
        return self

    def values(self):
        return _Values(self)

    def create(self, body):
        def run():
            for s in body["sheets"]:
                self.sheets[s["properties"]["title"]] = {"id": s["properties"]["sheetId"], "rows": []}
            return {"spreadsheetId": "SHEET123"}
        return _Call(run)

    def get(self, spreadsheetId, fields=None):
        return _Call(lambda: {"sheets": [{"properties": {"title": t, "sheetId": s["id"]}}
                                         for t, s in self.sheets.items()]})

    def batchUpdate(self, spreadsheetId, body):
        def run():
            for r in body["requests"]:
                self.requests.append(r)
                if "addSheet" in r:
                    p = r["addSheet"]["properties"]
                    self.sheets[p["title"]] = {"id": p["sheetId"], "rows": []}
                elif "updateCells" in r:
                    u = r["updateCells"]
                    title = next(t for t, s in self.sheets.items() if s["id"] == u["range"]["sheetId"])
                    for i, row in enumerate(u["rows"]):
                        for j, cell in enumerate(row["values"]):
                            v = next(iter(cell["userEnteredValue"].values()))
                            self.set_cell(title, u["range"]["startRowIndex"] + i, u["range"]["startColumnIndex"] + j, v)
                elif "deleteSheet" in r:
                    sid = r["deleteSheet"]["sheetId"]
                    self.sheets = {t: s for t, s in self.sheets.items() if s["id"] != sid}
                elif "deleteDimension" in r:
                    rng = r["deleteDimension"]["range"]
                    sheet = next(s for s in self.sheets.values() if s["id"] == rng["sheetId"])
                    del sheet["rows"][rng["startIndex"]:rng["endIndex"]]
            return {}
        return _Call(run)

    def set_cell(self, title, row, col, value):
        rows = self.sheets[title]["rows"]
        while len(rows) <= row:
            rows.append([])
        while len(rows[row]) <= col:
            rows[row].append("")
        rows[row][col] = value


class _Values:
    def __init__(self, fake):
        self.fake = fake

    def get(self, spreadsheetId, range, **_):
        def run():
            title, r0, r1, c0, c1 = _parse_a1(range)
            rows = self.fake.sheets[title]["rows"]
            out = [row[c0:c1 + 1] for row in rows[r0:None if r1 is None else r1 + 1]]
            while out and not any(out[-1]):
                out.pop()
            return {"values": out} if out else {}
        return _Call(run)

    def update(self, spreadsheetId, range, valueInputOption, body):
        def run():
            title, r0, _, c0, _ = _parse_a1(range)
            for i, row in enumerate(body["values"]):
                for j, v in enumerate(row):
                    self.fake.set_cell(title, r0 + i, c0 + j, v)
            return {}
        return _Call(run)

    def batchUpdate(self, spreadsheetId, body):
        def run():
            for d in body["data"]:
                self.update(spreadsheetId, d["range"], body["valueInputOption"], {"values": d["values"]}).execute()
            return {}
        return _Call(run)
