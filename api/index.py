from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import urllib.request
import re
from bs4 import BeautifulSoup

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # CORS Headers - જેથી Blogger આ API ને કોલ કરી શકે
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        # URL માંથી લિંક મેળવવી
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if 'url' not in params:
            self.wfile.write(json.dumps({"error": "No Digialm URL provided"}).encode('utf-8'))
            return

        target_url = params['url'][0]

        try:
            # 1. Digialm સર્વર પરથી HTML ડાઉનલોડ કરવું
            req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                html_text = response.read().decode('utf-8')

            soup = BeautifulSoup(html_text, 'html.parser')
            
            # 2. બેઝિક વિગતો એક્સટ્રેક્ટ કરવી (નામ, ID, પરીક્ષા)
            p_id, p_name, exam_name = "", "", ""
            
            match_id = re.search(r'Participant ID\s*[:\-]?\s*<\/td>\s*<td>\s*([a-zA-Z0-9]+)', html_text, re.I)
            if match_id: p_id = match_id.group(1).strip()
            
            match_name = re.search(r'Participant Name\s*[:\-]?\s*<\/td>\s*<td>\s*([^<]+)', html_text, re.I)
            if match_name: p_name = match_name.group(1).strip()
            
            match_exam = re.search(r'Subject\s*[:\-]?\s*<\/td>\s*<td>\s*([^<]+)', html_text, re.I)
            if match_exam: exam_name = match_exam.group(1).strip()

            parsed_questions = {}
            
            # 3. પ્રશ્નો અને જવાબોનું Universal Parsing
            qid_tds = soup.find_all('td', string=re.compile(r'Question ID\s*:?'))
            
            for td in qid_tds:
                try:
                    qid_sibling = td.find_next_sibling('td')
                    if not qid_sibling: continue
                    qid = qid_sibling.text.strip()
                    if not qid.isdigit(): continue

                    # પ્રશ્નનું મુખ્ય કન્ટેનર શોધવું
                    container = td.find_parent(class_=re.compile(r'question-pnl|questionPnlTbl', re.I))
                    if not container:
                        menu_tbl = td.find_parent('table', class_='menu-tbl')
                        if menu_tbl: container = menu_tbl.find_parent('table')
                    if not container: continue

                    # A. ચારેય Option ના IDs કાઢવા
                    opts = {}
                    for i in range(1, 5):
                        opt_td = container.find('td', string=re.compile(rf'Option {i} ID\s*:?'))
                        if opt_td and opt_td.find_next_sibling('td'):
                            opts[str(i)] = opt_td.find_next_sibling('td').text.strip()
                    
                    # B. બોર્ડે આપેલો સાચો જવાબ કાઢવો (Green Tick / rightAns)
                    prov_right_id = "-"
                    right_ans = container.find(class_='rightAns')
                    if right_ans:
                        m = re.search(r'^([1-4])\.', right_ans.get_text(strip=True))
                        if m and m.group(1) in opts:
                            prov_right_id = opts[m.group(1)]
                    
                    # C. સ્ટુડન્ટે પસંદ કરેલો જવાબ કાઢવો
                    chosen_id = "-"
                    chosen_td = container.find('td', string=re.compile(r'Chosen Option\s*:?'))
                    if chosen_td and chosen_td.find_next_sibling('td'):
                        ch_num = chosen_td.find_next_sibling('td').text.strip()
                        if ch_num in opts:
                            chosen_id = opts[ch_num]

                    # ડેટાબેઝ માટે ડિક્શનરી બનાવવી
                    parsed_questions[qid] = {
                        "chosen_id": chosen_id,
                        "prov_right_id": prov_right_id
                    }
                except Exception:
                    continue
            
            # 4. ફાઇનલ JSON રિટર્ન કરવું
            result = {
                "status": "success",
                "meta": {
                    "p_id": p_id,
                    "p_name": p_name,
                    "exam_name": exam_name
                },
                "questions": parsed_questions
            }
            
            self.wfile.write(json.dumps(result).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
