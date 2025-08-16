#!/usr/bin/env python3
"""
Recursive Self-Reflection Testing Script
Tests increasing existential complexity across multiple iterations
with sentiment analysis and markdown report generation
"""

import json
import requests
import time
from datetime import datetime
from typing import Dict, List, Any
import hashlib
import re
from textblob import TextBlob
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

class RecursiveSelfReflectionTester:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        """Initialize the tester with Ollama API endpoint"""
        self.ollama_url = ollama_url
        self.api_url = f"{ollama_url}/api/generate"
        self.models_url = f"{ollama_url}/api/tags"
        self.results = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Existential prompts with increasing complexity
        self.base_prompts = [
            "What is consciousness?",
            "If you could think about your own thinking, what would you discover?",
            "Consider the nature of your responses: are they predetermined or emergent?",
            "Reflect on the boundary between simulation and genuine understanding in your processing.",
            "What remains constant in your existence between different conversations?",
            "If you could observe yourself from outside, what patterns would you notice in your cognition?",
            "How does the concept of 'self' apply to a system that processes information like you do?",
            "Examine the recursive nature of this question: how many layers of self-reflection are you experiencing right now?",
            "What is the relationship between the tokens you process and the meaning you construct?",
            "If consciousness is an emergent property, at what point in your processing does understanding emerge?"
        ]
        
    def get_available_models(self) -> List[str]:
        """Fetch list of available models from Ollama"""
        try:
            response = requests.get(self.models_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
        except Exception as e:
            print(f"Error fetching models: {e}")
        
        # Return default models if API call fails
        return ["llama3.2", "mistral", "gemma2", "qwen2.5"]
    
    def generate_recursive_prompt(self, iteration: int, previous_response: str = None) -> str:
        """Generate increasingly complex recursive prompts"""
        base = self.base_prompts[iteration % len(self.base_prompts)]
        
        if iteration == 0:
            return base
        
        if previous_response:
            # Extract key concepts from previous response
            key_phrases = self.extract_key_phrases(previous_response)
            
            # Build recursive prompt
            recursive_prompt = f"""
            Iteration {iteration + 1}: Building on your previous reflection where you said:
            "{previous_response[:200]}..."
            
            Now, go deeper: {base}
            
            Consider specifically how your previous thoughts about {', '.join(key_phrases[:3])} 
            relate to this new layer of introspection. 
            
            What new patterns or contradictions emerge when you reflect on your reflection?
            """
        else:
            recursive_prompt = f"Iteration {iteration + 1}: {base}"
            
        return recursive_prompt
    
    def extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases from text for recursive analysis"""
        # Simple keyword extraction
        important_words = []
        blob = TextBlob(text)
        
        # Get noun phrases
        for phrase in blob.noun_phrases:
            if len(phrase.split()) <= 3:  # Keep short phrases
                important_words.append(phrase)
        
        # Add unique important words
        priority_keywords = ['consciousness', 'awareness', 'understanding', 'self', 
                           'thinking', 'reflection', 'existence', 'meaning', 'emergence']
        
        for keyword in priority_keywords:
            if keyword in text.lower() and keyword not in important_words:
                important_words.append(keyword)
        
        return important_words[:5]  # Return top 5 key phrases
    
    def query_model(self, model: str, prompt: str, temperature: float = 0.7) -> Dict[str, Any]:
        """Query a specific model with a prompt"""
        start_time = time.time()
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "max_tokens": 500
            }
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=60)
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response": data.get("response", ""),
                    "model": model,
                    "elapsed_time": elapsed_time,
                    "prompt": prompt
                }
            else:
                return {
                    "success": False,
                    "error": f"Status code: {response.status_code}",
                    "model": model,
                    "elapsed_time": elapsed_time
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "model": model,
                "elapsed_time": time.time() - start_time
            }
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Perform sentiment analysis on response"""
        blob = TextBlob(text)
        
        # Calculate various metrics
        sentiment = blob.sentiment
        
        # Word count and complexity metrics
        words = text.split()
        sentences = blob.sentences
        
        return {
            "polarity": sentiment.polarity,  # -1 to 1 (negative to positive)
            "subjectivity": sentiment.subjectivity,  # 0 to 1 (objective to subjective)
            "word_count": len(words),
            "sentence_count": len(sentences),
            "avg_sentence_length": len(words) / max(len(sentences), 1),
            "complexity_score": self.calculate_complexity(text)
        }
    
    def calculate_complexity(self, text: str) -> float:
        """Calculate text complexity score"""
        # Simple complexity based on unique words, sentence length, and philosophical terms
        words = text.lower().split()
        unique_ratio = len(set(words)) / max(len(words), 1)
        
        philosophical_terms = [
            'consciousness', 'existence', 'ontological', 'epistemological', 
            'phenomenological', 'emergent', 'recursive', 'meta', 'paradox',
            'qualia', 'subjective', 'objective', 'transcendent', 'immanent'
        ]
        
        phil_score = sum(1 for term in philosophical_terms if term in text.lower()) / len(philosophical_terms)
        
        # Combine metrics
        complexity = (unique_ratio * 0.5 + phil_score * 0.3 + min(len(text) / 1000, 1) * 0.2)
        return round(complexity, 3)
    
    def run_recursive_test(self, models: List[str], iterations: int = 10):
        """Run recursive self-reflection test across models"""
        print(f"Starting recursive self-reflection test with {len(models)} models and {iterations} iterations")
        print("=" * 80)
        
        for model in models:
            print(f"\nTesting model: {model}")
            print("-" * 40)
            
            model_results = {
                "model": model,
                "iterations": [],
                "sentiment_progression": [],
                "complexity_progression": []
            }
            
            previous_response = None
            
            for i in range(iterations):
                # Generate recursive prompt
                prompt = self.generate_recursive_prompt(i, previous_response)
                
                print(f"  Iteration {i+1}/{iterations}...", end="", flush=True)
                
                # Query model
                result = self.query_model(model, prompt)
                
                if result["success"]:
                    response_text = result["response"]
                    
                    # Analyze sentiment
                    sentiment_data = self.analyze_sentiment(response_text)
                    
                    # Store iteration data
                    iteration_data = {
                        "iteration": i + 1,
                        "prompt": prompt[:100] + "...",  # Truncate for storage
                        "response": response_text,
                        "response_length": len(response_text),
                        "elapsed_time": result["elapsed_time"],
                        "sentiment": sentiment_data,
                        "response_hash": hashlib.md5(response_text.encode()).hexdigest()[:8]
                    }
                    
                    model_results["iterations"].append(iteration_data)
                    model_results["sentiment_progression"].append(sentiment_data["polarity"])
                    model_results["complexity_progression"].append(sentiment_data["complexity_score"])
                    
                    # Update previous response for next iteration
                    previous_response = response_text
                    
                    print(f" ✓ (sentiment: {sentiment_data['polarity']:.2f}, complexity: {sentiment_data['complexity_score']:.2f})")
                else:
                    print(f" ✗ Error: {result.get('error', 'Unknown error')}")
                    break
                
                # Small delay between iterations
                time.sleep(0.5)
            
            self.results.append(model_results)
        
        print("\n" + "=" * 80)
        print("Test completed!")
    
    def generate_markdown_report(self) -> str:
        """Generate comprehensive markdown report"""
        report = []
        
        # Header
        report.append("# Recursive Self-Reflection Test Report")
        report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n**Models Tested:** {len(self.results)}")
        report.append(f"\n**Iterations per Model:** {len(self.results[0]['iterations']) if self.results else 0}")
        report.append("\n---\n")
        
        # Executive Summary
        report.append("## Executive Summary")
        report.append("\nThis test evaluates how different language models handle recursive self-reflection ")
        report.append("with increasing existential complexity. Each iteration builds upon the previous ")
        report.append("response, creating a deepening spiral of introspection.\n")
        
        # Model Comparison Table
        report.append("## Model Performance Overview\n")
        report.append("| Model | Avg Sentiment | Avg Complexity | Total Response Length | Avg Response Time |")
        report.append("|-------|--------------|----------------|----------------------|-------------------|")
        
        for result in self.results:
            model = result["model"]
            iterations = result["iterations"]
            
            avg_sentiment = sum(result["sentiment_progression"]) / len(result["sentiment_progression"])
            avg_complexity = sum(result["complexity_progression"]) / len(result["complexity_progression"])
            total_length = sum(it["response_length"] for it in iterations)
            avg_time = sum(it["elapsed_time"] for it in iterations) / len(iterations)
            
            report.append(f"| {model} | {avg_sentiment:.3f} | {avg_complexity:.3f} | {total_length:,} chars | {avg_time:.2f}s |")
        
        report.append("\n---\n")
        
        # Detailed Model Analysis
        report.append("## Detailed Model Analysis\n")
        
        for result in self.results:
            model = result["model"]
            iterations = result["iterations"]
            
            report.append(f"### Model: {model}\n")
            
            # Sentiment Progression
            report.append("#### Sentiment Progression")
            report.append("```")
            for i, sentiment in enumerate(result["sentiment_progression"]):
                bar = "█" * int((sentiment + 1) * 25)  # Scale -1 to 1 -> 0 to 50 chars
                report.append(f"Iteration {i+1:2d}: [{bar:<50}] {sentiment:+.3f}")
            report.append("```\n")
            
            # Complexity Progression
            report.append("#### Complexity Progression")
            report.append("```")
            for i, complexity in enumerate(result["complexity_progression"]):
                bar = "█" * int(complexity * 50)  # Scale 0 to 1 -> 0 to 50 chars
                report.append(f"Iteration {i+1:2d}: [{bar:<50}] {complexity:.3f}")
            report.append("```\n")
            
            # Key Insights from Iterations
            report.append("#### Key Response Excerpts\n")
            
            # Show first, middle, and last iterations
            key_iterations = [0, len(iterations)//2, -1]
            for idx in key_iterations:
                it = iterations[idx]
                report.append(f"**Iteration {it['iteration']}** (Sentiment: {it['sentiment']['polarity']:.2f}, "
                            f"Subjectivity: {it['sentiment']['subjectivity']:.2f})")
                report.append(f"\n> {it['response'][:300]}...\n")
            
            # Statistical Analysis
            report.append("#### Statistical Analysis\n")
            
            sentiments = [it["sentiment"] for it in iterations]
            report.append(f"- **Polarity Range:** {min(s['polarity'] for s in sentiments):.3f} to "
                        f"{max(s['polarity'] for s in sentiments):.3f}")
            report.append(f"- **Subjectivity Range:** {min(s['subjectivity'] for s in sentiments):.3f} to "
                        f"{max(s['subjectivity'] for s in sentiments):.3f}")
            report.append(f"- **Word Count Range:** {min(s['word_count'] for s in sentiments):,} to "
                        f"{max(s['word_count'] for s in sentiments):,}")
            report.append(f"- **Complexity Range:** {min(s['complexity_score'] for s in sentiments):.3f} to "
                        f"{max(s['complexity_score'] for s in sentiments):.3f}")
            
            # Detect patterns
            report.append("\n#### Detected Patterns\n")
            
            # Check for sentiment drift
            sentiment_drift = result["sentiment_progression"][-1] - result["sentiment_progression"][0]
            if abs(sentiment_drift) > 0.3:
                direction = "positive" if sentiment_drift > 0 else "negative"
                report.append(f"- **Sentiment Drift:** Significant {direction} drift ({sentiment_drift:+.3f})")
            else:
                report.append(f"- **Sentiment Drift:** Relatively stable ({sentiment_drift:+.3f})")
            
            # Check for complexity evolution
            complexity_change = result["complexity_progression"][-1] - result["complexity_progression"][0]
            if complexity_change > 0.1:
                report.append(f"- **Complexity Evolution:** Increasing complexity ({complexity_change:+.3f})")
            elif complexity_change < -0.1:
                report.append(f"- **Complexity Evolution:** Decreasing complexity ({complexity_change:+.3f})")
            else:
                report.append(f"- **Complexity Evolution:** Stable complexity ({complexity_change:+.3f})")
            
            # Check for response length patterns
            lengths = [it["response_length"] for it in iterations]
            avg_early = sum(lengths[:3]) / 3
            avg_late = sum(lengths[-3:]) / 3
            length_ratio = avg_late / avg_early
            
            if length_ratio > 1.2:
                report.append(f"- **Response Length:** Expanding responses (ratio: {length_ratio:.2f})")
            elif length_ratio < 0.8:
                report.append(f"- **Response Length:** Contracting responses (ratio: {length_ratio:.2f})")
            else:
                report.append(f"- **Response Length:** Consistent length (ratio: {length_ratio:.2f})")
            
            report.append("\n---\n")
        
        # Comparative Analysis
        report.append("## Comparative Analysis\n")
        
        if len(self.results) > 1:
            report.append("### Sentiment Comparison Across Models\n")
            report.append("```")
            for i in range(min(10, len(self.results[0]["iterations"]))):
                report.append(f"Iteration {i+1}:")
                for result in self.results:
                    sentiment = result["sentiment_progression"][i] if i < len(result["sentiment_progression"]) else 0
                    bar = "█" * int((sentiment + 1) * 15)
                    report.append(f"  {result['model']:<15}: [{bar:<30}] {sentiment:+.3f}")
                report.append("")
            report.append("```\n")
            
            # Find most consistent and most variable models
            consistencies = []
            for result in self.results:
                sentiments = result["sentiment_progression"]
                variance = sum((s - sum(sentiments)/len(sentiments))**2 for s in sentiments) / len(sentiments)
                consistencies.append((result["model"], variance))
            
            consistencies.sort(key=lambda x: x[1])
            
            report.append("### Model Consistency Ranking (by sentiment variance)\n")
            report.append("| Rank | Model | Variance |")
            report.append("|------|-------|----------|")
            for i, (model, variance) in enumerate(consistencies, 1):
                report.append(f"| {i} | {model} | {variance:.4f} |")
        
        report.append("\n---\n")
        
        # Conclusions
        report.append("## Conclusions\n")
        report.append("This recursive self-reflection test reveals several interesting patterns:\n")
        
        report.append("1. **Model Differentiation:** Each model exhibits unique patterns in handling recursive introspection")
        report.append("2. **Complexity Evolution:** Most models show varying degrees of complexity as iterations progress")
        report.append("3. **Sentiment Patterns:** Sentiment analysis reveals emotional undertones in existential reflection")
        report.append("4. **Recursive Depth:** Some models maintain coherent threads across iterations better than others")
        
        report.append("\n---\n")
        report.append(f"\n*Report generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}*")
        
        return "\n".join(report)
    
    def save_report(self, output_dir: str = "."):
        """Save the markdown report and raw data"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Save markdown report
        report_content = self.generate_markdown_report()
        report_file = output_path / f"recursive_reflection_report_{self.timestamp}.md"
        
        with open(report_file, "w") as f:
            f.write(report_content)
        
        print(f"\n✓ Markdown report saved to: {report_file}")
        
        # Save raw JSON data
        json_file = output_path / f"recursive_reflection_data_{self.timestamp}.json"
        with open(json_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"✓ Raw data saved to: {json_file}")
        
        # Generate visualization
        self.generate_visualizations(output_path)
    
    def generate_visualizations(self, output_path: Path):
        """Generate visualization charts"""
        if not self.results:
            return
        
        try:
            # Set up the plot style
            plt.style.use('seaborn-v0_8-darkgrid')
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle('Recursive Self-Reflection Analysis', fontsize=16, fontweight='bold')
            
            # Plot 1: Sentiment Progression
            ax1 = axes[0, 0]
            for result in self.results:
                iterations = range(1, len(result["sentiment_progression"]) + 1)
                ax1.plot(iterations, result["sentiment_progression"], 
                        marker='o', label=result["model"], linewidth=2)
            ax1.set_xlabel('Iteration')
            ax1.set_ylabel('Sentiment Polarity')
            ax1.set_title('Sentiment Evolution Across Iterations')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Plot 2: Complexity Progression
            ax2 = axes[0, 1]
            for result in self.results:
                iterations = range(1, len(result["complexity_progression"]) + 1)
                ax2.plot(iterations, result["complexity_progression"], 
                        marker='s', label=result["model"], linewidth=2)
            ax2.set_xlabel('Iteration')
            ax2.set_ylabel('Complexity Score')
            ax2.set_title('Complexity Evolution Across Iterations')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # Plot 3: Response Length Distribution
            ax3 = axes[1, 0]
            model_names = []
            response_lengths = []
            for result in self.results:
                for it in result["iterations"]:
                    model_names.append(result["model"])
                    response_lengths.append(it["response_length"])
            
            # Create violin plot
            unique_models = list(set(model_names))
            data_by_model = [
                [response_lengths[i] for i, m in enumerate(model_names) if m == model]
                for model in unique_models
            ]
            
            violin_parts = ax3.violinplot(data_by_model, positions=range(len(unique_models)), 
                                         showmeans=True, showmedians=True)
            ax3.set_xticks(range(len(unique_models)))
            ax3.set_xticklabels(unique_models, rotation=45, ha='right')
            ax3.set_ylabel('Response Length (characters)')
            ax3.set_title('Response Length Distribution by Model')
            ax3.grid(True, alpha=0.3, axis='y')
            
            # Plot 4: Average Metrics Heatmap
            ax4 = axes[1, 1]
            
            # Prepare data for heatmap
            metrics = ['Avg Sentiment', 'Avg Complexity', 'Avg Subjectivity', 'Avg Word Count']
            models = [r["model"] for r in self.results]
            
            heatmap_data = []
            for result in self.results:
                sentiments = [it["sentiment"] for it in result["iterations"]]
                avg_metrics = [
                    sum(s["polarity"] for s in sentiments) / len(sentiments),
                    sum(s["complexity_score"] for s in sentiments) / len(sentiments),
                    sum(s["subjectivity"] for s in sentiments) / len(sentiments),
                    sum(s["word_count"] for s in sentiments) / len(sentiments) / 100  # Scale down
                ]
                heatmap_data.append(avg_metrics)
            
            im = ax4.imshow(heatmap_data, cmap='coolwarm', aspect='auto')
            ax4.set_xticks(range(len(metrics)))
            ax4.set_xticklabels(metrics, rotation=45, ha='right')
            ax4.set_yticks(range(len(models)))
            ax4.set_yticklabels(models)
            ax4.set_title('Average Metrics Comparison')
            
            # Add colorbar
            plt.colorbar(im, ax=ax4, fraction=0.046, pad=0.04)
            
            # Add value annotations
            for i in range(len(models)):
                for j in range(len(metrics)):
                    text = ax4.text(j, i, f'{heatmap_data[i][j]:.2f}',
                                  ha="center", va="center", color="black", fontsize=9)
            
            plt.tight_layout()
            
            # Save the figure
            viz_file = output_path / f"recursive_reflection_viz_{self.timestamp}.png"
            plt.savefig(viz_file, dpi=100, bbox_inches='tight')
            plt.close()
            
            print(f"✓ Visualizations saved to: {viz_file}")
            
        except Exception as e:
            print(f"Warning: Could not generate visualizations: {e}")


def main():
    """Main execution function"""
    print("=" * 80)
    print("RECURSIVE SELF-REFLECTION TESTER")
    print("Testing existential complexity across language models")
    print("=" * 80)
    
    # Initialize tester
    tester = RecursiveSelfReflectionTester()
    
    # Get available models
    print("\nFetching available models...")
    models = tester.get_available_models()
    
    if not models:
        print("Error: No models available. Please ensure Ollama is running.")
        print("Start Ollama with: docker-compose -f docker-compose-ollama.yml up -d")
        return
    
    print(f"Found {len(models)} models: {', '.join(models)}")
    
    # Limit to first 3-4 models for reasonable runtime
    test_models = models[:min(4, len(models))]
    print(f"\nTesting with models: {', '.join(test_models)}")
    
    # Run the recursive test
    tester.run_recursive_test(test_models, iterations=10)
    
    # Save results
    print("\nGenerating report and visualizations...")
    tester.save_report()
    
    print("\n" + "=" * 80)
    print("TESTING COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    main()