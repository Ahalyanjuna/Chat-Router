from flask import Flask, jsonify, request, render_template, redirect, url_for
import re
import os
from werkzeug.utils import secure_filename
from database import Database
from models import ProviderResponseGenerator

# Initialize Flask app and configure
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx', 'csv', 'xlsx', 'json', 'xml'}

# Create uploads directory if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = Database()

# Initialize database
db.init_db()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    """Get the file type category based on extension"""
    ext = filename.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        return 'PDF'
    elif ext in {'doc', 'docx'}:
        return 'Word Document'
    elif ext == 'txt':
        return 'Text File'
    elif ext == 'csv':
        return 'CSV'
    elif ext == 'xlsx':
        return 'Excel'
    elif ext == 'json':
        return 'JSON'
    elif ext == 'xml':
        return 'XML'
    return 'Unknown'

def format_file_size(size_in_bytes):
    """Convert file size to human readable format"""
    for unit in ['B', 'KB', 'MB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.1f} GB"

def process_file(file):
    """Process the uploaded file and return relevant information."""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        file_size = os.path.getsize(filepath)
        file_type = get_file_type(filename)
        
        return {
            "filename": filename,
            "original_name": file.filename,
            "size": file_size,
            "size_formatted": format_file_size(file_size),
            "type": file_type,
            "path": filepath
        }
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    rules = db.get_all_rules()
    models = db.get_all_models()
    return render_template('admin.html', rules=rules, models=models)

@app.route('/models', methods=['GET'])
def get_models():
    models = db.get_all_models()
    return jsonify(models)

@app.route('/api/rules', methods=['GET'])
def get_rules():
    rules = db.get_all_rules()
    return jsonify(rules)

@app.route('/api/rules', methods=['POST'])
def add_rule():
    data = request.json
    rule_id = db.add_rule(
        data['original_provider'],
        data['original_model'],
        data['regex_pattern'],
        data['redirect_provider'],
        data['redirect_model']
    )
    return jsonify({"id": rule_id, "message": "Rule added successfully"})

@app.route('/api/rules/<int:rule_id>', methods=['PUT'])
def update_rule(rule_id):
    data = request.json
    success = db.update_rule(
        rule_id,
        data['original_provider'],
        data['original_model'],
        data['regex_pattern'],
        data['redirect_provider'],
        data['redirect_model']
    )
    if success:
        return jsonify({"message": "Rule updated successfully"})
    return jsonify({"error": "Rule not found"}), 404

@app.route('/api/rules/<int:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    success = db.delete_rule(rule_id)
    if success:
        return jsonify({"message": "Rule deleted successfully"})
    return jsonify({"error": "Rule not found"}), 404


@app.route('/api/file-rules', methods=['GET'])
def get_file_rules():
    rules = db.get_file_routing_rules()
    return jsonify(rules)

@app.route('/api/file-rules', methods=['POST'])
def add_file_rule():
    data = request.json
    rule_id = db.add_file_rule(
        data['file_type'],
        data['redirect_provider'],
        data['redirect_model']
    )
    return jsonify({"id": rule_id, "message": "File rule added successfully"})

@app.route('/api/file-rules/<int:rule_id>', methods=['DELETE'])
def delete_file_rule(rule_id):
    success = db.delete_file_rule(rule_id)
    if success:
        return jsonify({"message": "File rule deleted successfully"})
    return jsonify({"error": "Rule not found"}), 404

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    # Get form data
    provider = request.form.get('provider')
    model = request.form.get('model')
    prompt = request.form.get('prompt')
    
    if not provider or not model:
        return jsonify({"error": "Missing required fields (provider or model)"}), 400
    
    # Store original provider and model for routing info
    original_provider = provider
    original_model = model
    
    # Initialize routing variables
    file_info = None
    routing_reason = None
    routing_result = None
    
    # Process file if uploaded
    if 'file' in request.files:
        file = request.files['file']
        if file.filename:
            file_info = process_file(file)
            if not file_info:
                return jsonify({
                    "error": f"Invalid file type. Allowed types are: {', '.join(ALLOWED_EXTENSIONS)}"
                }), 400
            
            # Check file routing rules first
            file_routing = db.get_file_routing(file_info['type'])
            if file_routing:
                provider, model = file_routing
                routing_reason = f"File type routing: {file_info['type']}"
                print(f"Routing file upload to {provider}/{model}")
    
    # If no prompt and no file, return error
    if not prompt and not file_info:
        return jsonify({"error": "Either prompt or file is required"}), 400
    
    # Check text routing rules only if there's a prompt and no file routing has occurred
    if prompt and not routing_reason:
        routing_result = db.check_routing_rules(provider, model, prompt)
        if routing_result:
            provider, model, pattern = routing_result
            pattern_text = pattern.replace('(?i)', '').strip('()')
            routing_reason = f"Regex pattern match: {pattern_text} mention"
            print(f"Redirecting {original_provider}/{original_model} to {provider}/{model}")
    
    # Generate response
    generator_class = ProviderResponseGenerator.get_generator(provider)
    
    # Construct appropriate prompt based on whether there's a file or text
    if file_info:
        final_prompt = f"Process uploaded {file_info['type']}: {file_info['original_name']}"
        if prompt:  # If there's also a text prompt, append it
            final_prompt += f"\nUser instructions: {prompt}"
    else:
        final_prompt = prompt
    
    response = generator_class.generate_response(model, final_prompt)
    
    # Add file information if present
    if file_info:
        response["file_info"] = {
            "filename": file_info["filename"],
            "original_name": file_info["original_name"],
            "size": file_info["size"],
            "size_formatted": file_info["size_formatted"],
            "type": file_info["type"]
        }
    
    # Add routing information if any redirection occurred
    if original_provider != provider or original_model != model:
        response["routing_info"] = {
            "original_provider": original_provider,
            "original_model": original_model,
            "redirected_to": f"{provider}/{model}",
            "reason": routing_reason
        }
    
    return jsonify(response)


if __name__ == '__main__':
    app.run(debug=True)