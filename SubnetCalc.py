from flask import Flask, render_template_string, request
import re

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Subnet Calculator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial; padding: 20px; max-width: 520px; margin: auto; transition: 0.3s; }
        input, button { width: 100%; padding: 10px; margin: 8px 0; font-size: 16px; }
        .result { padding: 12px; border-radius: 10px; margin-top:10px; }
        .error { color: red; }
        .binary { font-family: monospace; font-size: 14px; word-break: break-all; }
        .net { color: #4CAF50; }
        .host { color: #E53935; }
        .saved { padding:10px; border-radius:10px; margin-top:10px; }

        /* LIGHT MODE */
        body.light { background: #ffffff; color: #000; }
        body.light .result { background: #f4f4f4; }
        body.light .saved { background:#eef; }

        /* DARK MODE */
        body.dark { background: #121212; color: #fff; }
        body.dark .result { background: #1e1e1e; }
        body.dark input, body.dark button { background:#2a2a2a; color:#fff; border:1px solid #444; }
        body.dark .saved { background:#1e2a3a; }

        .toggle {
            margin-bottom: 10px;
            cursor: pointer;
            padding: 8px;
            border-radius: 8px;
            border: none;
        }
    </style>
</head>
<body class="light">

    <button class="toggle" onclick="toggleMode()">🌙 Toggle Dark Mode</button>

    <h2>Subnet Calculator 🚀</h2>

    <form method="post">
        <input type="text" name="ip" placeholder="Enter IP (192.168.1.10)" required autofocus>

        <label>CIDR: <span id="cidrVal">{{cidr if cidr is not none else 24}}</span></label>
        <input type="range" min="0" max="32" name="cidr" id="cidr"
               value="{{cidr if cidr is not none else 24}}"
               oninput="cidrVal.innerText=this.value">

        <button type="submit">Calculate</button>
    </form>

    {% if error %}
        <div class="error">{{error}}</div>
    {% endif %}

    {% if result %}
    <div class="result">
        <b>Network:</b> {{result.network}}<br>
        <b>Broadcast:</b> {{result.broadcast}}<br>
        <b>Usable Range:</b> {{result.first}} - {{result.last}}<br>
        <b>Total Hosts:</b> {{result.hosts}}<br>
        <b>Subnet Mask:</b> {{result.mask}}<br><br>

        <b>Binary (IP):</b><br>
        <div class="binary">{{result.ip_binary_colored|safe}}</div><br>

        <b>Binary (Mask):</b><br>
        <div class="binary">{{result.mask_binary_colored|safe}}</div>
    </div>

    <div class="result">
        <b>📘 Subnet Explanation:</b><br><br>
        • /{{result.cidr}} network<br>
        • Hosts = {{result.hosts}}<br>
        • Block size = {{result.block_size}}<br>
    </div>

    <script>
        let entry = "{{result.network}} | /{{result.cidr}}";
        let arr = JSON.parse(localStorage.getItem('subnets') || '[]');
        arr.unshift(entry);
        arr = arr.slice(0,5);
        localStorage.setItem('subnets', JSON.stringify(arr));
    </script>
    {% endif %}

    <div class="saved" id="saved"></div>

<script>
function renderSaved(){
    let arr = JSON.parse(localStorage.getItem('subnets') || '[]');
    document.getElementById('saved').innerHTML =
        '<b>Recent:</b><br>' + arr.map(a => `${a}`).join('<br>');
}

function toggleMode(){
    let body = document.body;
    if(body.classList.contains('light')){
        body.classList.remove('light');
        body.classList.add('dark');
        localStorage.setItem('theme','dark');
    } else {
        body.classList.remove('dark');
        body.classList.add('light');
        localStorage.setItem('theme','light');
    }
}

function loadTheme(){
    let theme = localStorage.getItem('theme');
    if(theme === 'dark'){
        document.body.classList.remove('light');
        document.body.classList.add('dark');
    }
}

renderSaved();
loadTheme();
</script>

</body>
</html>
"""

# ---------- Helpers ----------

def valid_ip(ip):
    pattern = r"^\d{1,3}(\.\d{1,3}){3}$"
    if not re.match(pattern, ip):
        return False
    return all(0 <= int(p) <= 255 for p in ip.split('.'))


def valid_cidr(cidr):
    return 0 <= cidr <= 32


def ip_to_int(ip):
    parts = list(map(int, ip.split('.')))
    return (parts[0]<<24) + (parts[1]<<16) + (parts[2]<<8) + parts[3]


def int_to_ip(i):
    return f"{(i>>24)&255}.{(i>>16)&255}.{(i>>8)&255}.{i&255}"


def to_binary(ip):
    return '.'.join(f"{int(o):08b}" for o in ip.split('.'))


def color_bits(binary, cidr):
    bits = binary.replace('.', '')
    colored = ''
    for i, b in enumerate(bits):
        if i < cidr:
            colored += f"<span class='net'>{b}</span>"
        else:
            colored += f"<span class='host'>{b}</span>"
        if (i+1) % 8 == 0 and i != 31:
            colored += '.'
    return colored


@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    error = None
    cidr_val = None

    if request.method == 'POST':
        ip = request.form['ip']
        try:
            cidr = int(request.form['cidr'])
            cidr_val = cidr
        except:
            cidr = -1

        if not valid_ip(ip):
            error = "Invalid IP address"
        elif not valid_cidr(cidr):
            error = "CIDR must be 0–32"
        else:
            ip_int = ip_to_int(ip)
            mask_int = (0xFFFFFFFF << (32 - cidr)) & 0xFFFFFFFF

            network = ip_int & mask_int
            broadcast = network | (~mask_int & 0xFFFFFFFF)

            first = network + 1 if cidr < 31 else network
            last = broadcast - 1 if cidr < 31 else broadcast
            hosts = (2 ** (32 - cidr)) - (2 if cidr < 31 else 0)

            mask = int_to_ip(mask_int)

            ip_bin = to_binary(ip)
            mask_bin = to_binary(mask)

            mask_octets = list(map(int, mask.split('.')))
            interesting = next((o for o in mask_octets if o != 255), 255)
            block_size = 256 - interesting if interesting != 255 else 1

            result = {
                'network': int_to_ip(network),
                'broadcast': int_to_ip(broadcast),
                'first': int_to_ip(first),
                'last': int_to_ip(last),
                'hosts': hosts,
                'mask': mask,
                'ip_binary_colored': color_bits(ip_bin, cidr),
                'mask_binary_colored': color_bits(mask_bin, cidr),
                'cidr': cidr,
                'block_size': block_size
            }

    return render_template_string(HTML, result=result, error=error, cidr=cidr_val)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
