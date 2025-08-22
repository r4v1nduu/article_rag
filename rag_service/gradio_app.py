import gradio as gr
import requests

# Try multiple URLs for RAG service
POSSIBLE_URLS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

def find_working_rag_service():
    """Find which RAG service URL is working"""
    for url in POSSIBLE_URLS:
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ Found working RAG service at: {url}")
                return url
        except:
            continue
    
    print("❌ No working RAG service found")
    return None

# Find working URL at startup
RAG_SERVICE_URL = find_working_rag_service()

def query_rag(question, num_docs, model_name):
    """Send question to RAG service and return answer"""
    if not RAG_SERVICE_URL:
        return "❌ RAG service not available. Check if it's running.", "No service found"
    
    if not question.strip():
        return "Please enter a question.", ""
    
    try:
        # Prepare request
        payload = {
            "query": question.strip(),
            "top_k": int(num_docs),
            "model": model_name
        }
        
        # Send request with longer timeout
        print(f"Sending query to {RAG_SERVICE_URL}")
        response = requests.post(
            f"{RAG_SERVICE_URL}/ask",
            json=payload,
            timeout=300  # 5 minute timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Format the answer
            answer = result["answer"]
            
            # Create metadata string
            metadata = f"""
📊 **Response Info:**
- ⏱️ Time: {result.get('processing_time', 0):.1f}s
- 📚 Sources: {result.get('sources_count', 0)} documents
- 🤖 Model: {model_name}
- 🔗 Service: {RAG_SERVICE_URL}

📄 **Retrieved Documents:**
"""
            
            # Add source documents if available
            if result.get("retrieved_documents"):
                for i, doc in enumerate(result["retrieved_documents"][:2], 1):  # Show max 2 docs
                    preview = doc[:400] + "..." if len(doc) > 400 else doc
                    metadata += f"\n**Document {i}:**\n{preview}\n\n---\n"
            else:
                metadata += "No source documents returned."
            
            return answer, metadata
            
        else:
            error_msg = f"❌ Error {response.status_code}: {response.text[:200]}"
            return error_msg, f"Service URL: {RAG_SERVICE_URL}"
            
    except requests.exceptions.Timeout:
        return "⏰ Request timed out. The query might be complex - this is normal for some questions.", f"Processing took longer than 5 minutes at {RAG_SERVICE_URL}"
        
    except requests.exceptions.ConnectionError:
        return f"🔌 Cannot connect to RAG service. Tried: {RAG_SERVICE_URL}", "Check if your service is running"
        
    except Exception as e:
        return f"💥 Error: {str(e)}", f"Service URL: {RAG_SERVICE_URL}"

def check_health():
    """Check if RAG service is running"""
    if not RAG_SERVICE_URL:
        return "❌ No RAG service URL found. Possible URLs tried:\n" + "\n".join(POSSIBLE_URLS)
    
    try:
        response = requests.get(f"{RAG_SERVICE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = "✅ Healthy" if data.get("status") == "healthy" else "⚠️ Degraded"
            
            health_info = f"**Service Status:** {status}\n"
            health_info += f"**URL:** {RAG_SERVICE_URL}\n\n"
            
            services = data.get("services", {})
            for service, state in services.items():
                emoji = "✅" if state == "healthy" else "❌"
                health_info += f"{emoji} **{service.title()}**: {state}\n"
            
            return health_info
        else:
            return f"❌ Service returned status {response.status_code} from {RAG_SERVICE_URL}"
    except Exception as e:
        return f"❌ Cannot reach service: {str(e)}\n\nTrying URL: {RAG_SERVICE_URL}"

def get_stats():
    """Get service statistics"""
    if not RAG_SERVICE_URL:
        return "❌ No RAG service available"
    
    try:
        response = requests.get(f"{RAG_SERVICE_URL}/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            
            stats_text = f"""📊 **Service Statistics**

🔗 **URL:** {RAG_SERVICE_URL}
📞 **Total Requests:** {stats.get('total_requests', 'N/A')}
📚 **Documents:** {stats.get('documents_in_collection', 'N/A')}
🗃️ **Collection:** {stats.get('collection_name', 'N/A')}

🔗 **Backend Services:**
"""
            services = stats.get('services', {})
            for name, url in services.items():
                stats_text += f"- **{name.title()}:** {url}\n"
            
            return stats_text
        else:
            return f"❌ Could not get stats (Status: {response.status_code})"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="RAG Assistant", theme=gr.themes.Soft()) as demo:
    
    if RAG_SERVICE_URL:
        status_msg = f"🟢 Connected to RAG service at: {RAG_SERVICE_URL}"
    else:
        status_msg = f"🔴 RAG service not found. Tried: {', '.join(POSSIBLE_URLS)}"
    
    gr.Markdown(f"""
    # 🤖 RAG Assistant
    Ask questions about your document collection and get AI-powered answers.
    
    **Status:** {status_msg}
    """)
    
    with gr.Row():
        with gr.Column(scale=2):
            # Main chat interface
            question_input = gr.Textbox(
                label="💬 Ask a Question",
                placeholder="What would you like to know about your documents?",
                lines=2
            )
            
            with gr.Row():
                submit_btn = gr.Button("🚀 Ask", variant="primary", scale=1)
                clear_btn = gr.Button("🗑️ Clear", scale=1)
            
            answer_output = gr.Textbox(
                label="🤖 Answer",
                lines=10,
                interactive=False
            )
            
            sources_output = gr.Markdown(
                label="📚 Sources & Details",
                value="Ask a question to see sources and response details."
            )
        
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Settings")
            
            model_dropdown = gr.Dropdown(
                choices=["mistral:latest", "llama2:latest", "codellama:latest"],
                value="mistral:latest",
                label="🤖 Model"
            )
            
            num_docs_slider = gr.Slider(
                minimum=1,
                maximum=10,
                value=3,
                step=1,
                label="📄 Number of Documents"
            )
            
            gr.Markdown("### 🔧 Service Status")
            
            health_btn = gr.Button("🏥 Check Health", size="sm")
            health_output = gr.Markdown("Click 'Check Health' to see status")
            
            stats_btn = gr.Button("📊 Get Stats", size="sm")
            stats_output = gr.Markdown("Click 'Get Stats' to see usage info")
            
            gr.Markdown("### 💡 Example Questions")
            gr.Markdown("""
            - "How to change CrowdStrike agent ID?"
            - "What are the security steps?"
            - "How to disable sensor tampering?"
            - "What registry keys to modify?"
            """)
            
            if not RAG_SERVICE_URL:
                gr.Markdown("""
                ### 🚨 Troubleshooting
                1. Check if your RAG service is running
                2. Verify the service is accessible
                3. Try: `curl http://localhost:8000/health`
                """)
    
    # Event handlers
    submit_btn.click(
        fn=query_rag,
        inputs=[question_input, num_docs_slider, model_dropdown],
        outputs=[answer_output, sources_output]
    )
    
    clear_btn.click(
        fn=lambda: ("", "", "Ask a question to see sources and response details."),
        outputs=[question_input, answer_output, sources_output]
    )
    
    health_btn.click(
        fn=check_health,
        outputs=[health_output]
    )
    
    stats_btn.click(
        fn=get_stats,
        outputs=[stats_output]
    )
    
    # Allow Enter key to submit
    question_input.submit(
        fn=query_rag,
        inputs=[question_input, num_docs_slider, model_dropdown],
        outputs=[answer_output, sources_output]
    )

# Launch the interface
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=True
    )
