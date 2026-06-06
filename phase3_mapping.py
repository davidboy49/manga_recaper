import os
import json
import re
import math
from openai import OpenAI

SCRIPT_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\script.txt"
CATALOG_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\scene_catalog.json"
TIMELINE_OUT_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\timeline_map.json"


def load_data(script_path=None, catalog_path=None):
    if script_path is None:
        script_path = SCRIPT_PATH
    if catalog_path is None:
        catalog_path = CATALOG_PATH

    if not os.path.exists(script_path) or not os.path.exists(catalog_path):
        raise FileNotFoundError(f"Missing script path ({script_path}) or catalog path ({catalog_path}).")
    with open(script_path, 'r', encoding='utf-8') as f:
        paragraphs = [line.strip() for line in f.readlines() if line.strip()]
    
    sentence_endings = re.compile(r'(?<=[.!?])\s+')
    script_lines = []
    for para in paragraphs:
        for s in sentence_endings.split(para):
            if s.strip():
                script_lines.append(s.strip())
                
    with open(catalog_path, 'r', encoding='utf-8') as f:
        scene_catalog = json.load(f)
    return script_lines, scene_catalog


def fallback_proportional_mapping(script_lines, scene_catalog):
    print("\n[*] Triggering proportional mathematical fallback mapping...")
    timeline = []
    num_lines = len(script_lines)
    num_panels = len(scene_catalog)
    for i in range(num_lines):
        panel_idx = min(math.floor((i / num_lines) * num_panels), num_panels - 1)
        timeline.append({
            "audio_file": f"line_{i:03d}.wav",
            "text": script_lines[i],
            "panel_file": scene_catalog[panel_idx]["panel_file"]
        })
    return timeline

def align_timeline(S, M, strictly_increasing=True):
    N = len(S)
    if N == 0 or M == 0:
        return []
    
    # dp[i][j] = (min_cost, parent_j)
    dp = [[(float('inf'), -1) for _ in range(M)] for _ in range(N)]
    
    # Base case: first sentence
    for j in range(M):
        dp[0][j] = (abs(j - S[0]), -1)
        
    # Fill DP table
    for i in range(1, N):
        prefix_mins = []  # stores (min_val, min_k)
        running_min_val = float('inf')
        running_min_k = -1
        for k in range(M):
            val = dp[i-1][k][0]
            if val < running_min_val:
                running_min_val = val
                running_min_k = k
            prefix_mins.append((running_min_val, running_min_k))
            
        for j in range(M):
            cost = abs(j - S[i])
            limit_k = j - 1 if strictly_increasing else j
            if limit_k >= 0 and limit_k < M:
                min_val, min_k = prefix_mins[limit_k]
                if min_val != float('inf'):
                    dp[i][j] = (cost + min_val, min_k)
                    
    # Find the best ending panel for the last sentence
    best_cost = float('inf')
    best_j = -1
    for j in range(M):
        if dp[N-1][j][0] < best_cost:
            best_cost = dp[N-1][j][0]
            best_j = j
            
    if best_j == -1:
        if strictly_increasing:
            print("[*] Warning: strictly increasing alignment failed. Falling back to non-decreasing...")
            return align_timeline(S, M, strictly_increasing=False)
        else:
            print("[*] Warning: DP alignment failed completely. Using simple proportional fallback...")
            return [min(math.floor((idx / N) * M), M - 1) for idx in range(N)]
        
    # Reconstruct path
    path = []
    curr_j = best_j
    for i in range(N-1, -1, -1):
        path.append(curr_j)
        curr_j = dp[i][curr_j][1]
    path.reverse()
    return path


def extract_json_from_text(text):
    """Clean reasoning tags and extract JSON blocks from model outputs."""
    # Strip <think>...</think> tags if present
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # Try finding markdown code block: ```json ... ```
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
        
    # Find first opening bracket '[' and last closing bracket ']'
    match_arr = re.search(r'\[\s*\{.*\}\s*\]', text, flags=re.DOTALL)
    if match_arr:
        return match_arr.group(0).strip()
        
    return text.strip()


def get_cosine_similarity(text1, text2):
    import re, collections, math
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'in', 'on', 'at', 'to', 'from', 'by', 'for', 'with', 'about', 'against', 'between', 'into',
        'through', 'during', 'before', 'after', 'above', 'below', 'of', 'up', 'down', 'out',
        'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
        'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
        'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can',
        'will', 'just', 'don', 'should', 'now', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours',
        'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
        'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs',
        'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'has',
        'have', 'had', 'having', 'do', 'does', 'did', 'doing', 'would', 'could', 'should', 'ought',
        # VLM tag noise words
        'panel', 'scene', 'image', 'picture', 'characters', 'character', 'core', 'action',
        'emotion', 'visual', 'tone', 'mood', 'facts', 'showing', 'depicts', 'depicting',
        'visible', 'description'
    }
    
    words1 = [w for w in re.findall(r'\w+', text1.lower()) if w not in stop_words and not w.isdigit()]
    words2 = [w for w in re.findall(r'\w+', text2.lower()) if w not in stop_words and not w.isdigit()]
    
    if not words1 or not words2:
        return 0.0
        
    counter1 = collections.Counter(words1)
    counter2 = collections.Counter(words2)
    
    all_words = set(counter1.keys()).union(set(counter2.keys()))
    
    dot_product = sum(counter1[w] * counter2[w] for w in all_words)
    mag1 = math.sqrt(sum(counter1[w]**2 for w in counter1))
    mag2 = math.sqrt(sum(counter2[w]**2 for w in counter2))
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot_product / (mag1 * mag2)


def run_mapping(script_path=None, catalog_path=None, timeline_out_path=None, api_url=None, api_key=None, model=None):
    if script_path is None:
        script_path = SCRIPT_PATH
    if catalog_path is None:
        catalog_path = CATALOG_PATH
    if timeline_out_path is None:
        timeline_out_path = TIMELINE_OUT_PATH

    print("[*] Starting Phase 3: Timeline Mapping (Optimized Local Heuristic Matcher)...")
    try:
        script_lines, scene_catalog = load_data(script_path, catalog_path)
    except Exception as e:
        print(f"[!] Error loading inputs: {e}")
        return

    num_lines = len(script_lines)
    num_panels = len(scene_catalog)
    
    S = []
    
    names = ["eugene", "hamel", "vermouth", "senya", "anise", "gordon", "father", "wife", "concubine", "lionhart", "wise", "great", "faithful", "brave"]
    keywords = ["sword", "dummy", "carriage", "portal", "fight", "train", "ritual", "shield", "axe", "monster", "castle", "forest", "gate", "dummy", "wood", "blacksmith", "magic", "blood"]
    
    for i, line in enumerate(script_lines):
        line_lower = line.lower()
        best_j = -1
        best_score = -float('inf')
        
        for j, panel in enumerate(scene_catalog):
            desc_lower = panel["description"].lower()
            
            # 1. Cosine similarity
            sim = get_cosine_similarity(line_lower, desc_lower)
            
            # 2. Character name overlap boost
            name_bonus = 0.0
            for name in names:
                if name in line_lower and name in desc_lower:
                    name_bonus += 0.4
                    
            # 3. Action/keyword boost
            keyword_bonus = 0.0
            for kw in keywords:
                if kw in line_lower and kw in desc_lower:
                    keyword_bonus += 0.2
                    
            # 4. Chronological distance penalty to prevent out-of-order jumps
            prop_j = (i / num_lines) * num_panels
            dist_penalty = 0.08 * abs(j - prop_j)
            
            score = sim + name_bonus + keyword_bonus - dist_penalty
            if score > best_score:
                best_score = score
                best_j = j
                
        S.append(best_j)
        
    # Solve alignment sequence globally using DP
    strictly_increasing = (num_lines <= num_panels)
    print(f"[*] Solving global sequence alignment (strictly_increasing={strictly_increasing}, lines={num_lines}, panels={num_panels})...")
    path = align_timeline(S, num_panels, strictly_increasing=strictly_increasing)
    
    timeline = []
    for i, line in enumerate(script_lines):
        panel_idx = path[i]
        panel_file = scene_catalog[panel_idx]["panel_file"]
        timeline.append({
            "audio_file": f"line_{i:03d}.wav",
            "text": line,
            "panel_file": panel_file
        })
        
    print(f"[*] Successfully aligned and mapped all {len(timeline)} scenes.")
    
    # Save output map
    try:
        with open(timeline_out_path, 'w', encoding='utf-8') as f:
            json.dump(timeline, f, indent=4)
        print(f"[*] Timeline saved to {timeline_out_path}")
    except Exception as e:
        print(f"[!] Error saving timeline: {e}")


if __name__ == "__main__":
    run_mapping()