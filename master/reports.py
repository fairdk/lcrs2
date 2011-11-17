#
# LCRS Copyright (C) 2009-2011
# - Benjamin Bach
#
# LCRS is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# LCRS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with LCRS.  If not, see <http://www.gnu.org/licenses/>.

from datetime import datetime
REPORT_TEMPLATE_HTML = "report_template.html"

def make_report(groups, fmt, template=None):
    
    if not template:
        if fmt == "html":
            template = REPORT_TEMPLATE_HTML
    
    f = file(template)
    
    data = f.readlines()
    data = "".join(data)
    
    data = data.replace("$report_date$", datetime.now().strftime("%D"))
    
    row_data = ""
    
    for group in groups:
        for computer in group.computers:
            if fmt == "html":
                if computer.hw_info:
                    html = "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s<br />%s MB RAM</td></tr>" % (
                                computer.id,
                                computer.hw_info.get("BIOS S/N", ""),
                                computer.wipe_method.title() if computer.wiped else "Not wiped",
                                computer.wipe_finished_on.strftime("%D %T") if computer.wipe_finished_on else "-",
                                ["%s MB, S/N: %s" % (v["Size"], v["Serial"]) for v in computer.hw_info.get("Hard drives", {}).values()],
                                computer.hw_info.get("CPU", {}).get("name", "Unknown"),
                                computer.hw_info.get("Memory", 0),
                                )
                else:
                    html = "<tr><td>%s</td><td>-</td></tr>" % (computer.id,)
                
                row_data = row_data + html + "\n"
    
    print row_data
    data = data.replace("$report_rows$", row_data)
    
    return data
