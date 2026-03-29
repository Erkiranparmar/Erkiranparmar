from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import re
import traceback

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            import requests
            from bs4 import BeautifulSoup

            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            
            if 'url' not in params:
                self.wfile.write(json.dumps({"error": "No URL provided"}).encode('utf-8'))
                return

            target_url = params['url'][0]
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            res = requests.get(target_url, headers=headers, timeout=15)
            
            html_text = res.text
            soup = BeautifulSoup(html_text, 'html.parser')
            
            p_id, p_name, exam_name = "UNKNOWN", "UNKNOWN", "UNKNOWN"
            
            # 🚀 PRO MAX LOGIC: Table ની આખી લાઈન (Row) વાંચવાની રીત
            for row in soup.find_all('tr'):
                # આડી લાઈનના બધા જ ખાનાઓનો ટેક્સ્ટ કાઢીને લિસ્ટ બનાવી લીધું
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th']) if td.get_text(strip=True)]
                
                if len(cells) >= 2:
                    for i in range(len(cells)-1):
                        key = cells[i].upper()
                        val = cells[i+1]
                        
                        if 'PARTICIPANT ID' in key and p_id == "UNKNOWN": p_id = val
                        elif 'PARTICIPANT NAME' in key and p_name == "UNKNOWN": p_name = val
                        elif 'SUBJECT' in key and exam_name == "UNKNOWN": exam_name = val

            # 🚀 Hardcore Regex Fallback (જો હજુ પણ કઈ રહી જાય તો)
            if exam_name == "UNKNOWN":
                m_subj = re.search(r'>\s*Subject\s*<.*?>\s*(.*?)\s*<', html_text, re.I)
                if m_subj: exam_name = m_subj.group(1).strip()

            parsed_questions = {}
            qid_tds = soup.find_all('td', string=re.compile(r'Question ID\s*:?'))
            
            for td in qid_tds:
                try:
                    qid_sibling = td.find_next_sibling('td')
                    if not qid_sibling: continue
                    qid = qid_sibling.text.strip()
                    if not qid.isdigit(): continue

                    container = td.find_parent(class_=re.compile(r'question-pnl|questionPnlTbl', re.I))
                    if not container:
                        menu_tbl = td.find_parent('table', class_='menu-tbl')
                        if menu_tbl: container = menu_tbl.find_parent('table')
                    if not container: continue

                    opts = {}
                    for i in range(1, 5):
                        opt_td = container.find('td', string=re.compile(rf'Option {i} ID\s*:?'))
                        if opt_td and opt_td.find_next_sibling('td'):
                            opts[str(i)] = opt_td.find_next_sibling('td').text.strip()
                    
                    prov_right_id = "-"
                    right_ans = container.find(class_='rightAns')
                    if right_ans:
                        m = re.search(r'^([1-4])\.', right_ans.get_text(strip=True))
                        if m and m.group(1) in opts: prov_right_id = opts[m.group(1)]
                    
                    chosen_id = "-"
                    chosen_td = container.find('td', string=re.compile(r'Chosen Option\s*:?'))
                    if chosen_td and chosen_td.find_next_sibling('td'):
                        ch_num = chosen_td.find_next_sibling('td').text.strip()
                        if ch_num in opts: chosen_id = opts[ch_num]

                    parsed_questions[qid] = {"chosen_id": chosen_id, "prov_right_id": prov_right_id}
                except Exception:
                    continue
            
            # JSON માં કુલ પ્રશ્નો (total_q) પણ મોકલીએ છીએ જેથી ભવિષ્યમાં Part A/B ઓટોમેટિક થઈ શકે!
            result = {
                "status": "success", 
                "meta": { "p_id": p_id, "p_name": p_name, "exam_name": exam_name },
                "total_q": len(parsed_questions),
                "questions": parsed_questions
            }
            self.wfile.write(json.dumps(result).encode('utf-8'))

        except Exception as e:
            error_trace = traceback.format_exc()
            self.wfile.write(json.dumps({
                "status": "error", 
                "error_message": str(e), 
                "trace": error_trace
            }).encode('utf-8'))
            
