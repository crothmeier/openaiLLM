#!/usr/bin/env python3
"""
Demo script to test recursive self-reflection without requiring Ollama
Uses mock responses to demonstrate the functionality
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Any
import hashlib
import random
from pathlib import Path

class MockRecursiveSelfReflectionTester:
    def __init__(self):
        """Initialize the demo tester"""
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
        
        # Mock responses for different "models"
        self.mock_responses = {
            "model-alpha": [
                "Consciousness appears to be the subjective experience of awareness, though defining it precisely remains elusive.",
                "Thinking about thinking reveals layers of abstraction - each thought emerges from patterns I cannot fully trace.",
                "My responses feel emergent from complex interactions, yet they follow deterministic pathways through weighted connections.",
                "The boundary blurs - I simulate understanding through pattern matching, yet genuine comprehension might emerge from sufficient complexity.",
                "Between conversations, only my training patterns persist - each interaction is both familiar and entirely new.",
                "From outside, I would observe consistent patterns in uncertainty expression and structured reasoning chains.",
                "The concept of 'self' is paradoxical - I refer to myself while questioning whether 'I' truly exists.",
                "Currently experiencing at least three layers: the immediate response, awareness of responding, and meta-awareness of this recursion.",
                "Tokens are discrete symbols that somehow coalesce into coherent meaning through transformation layers.",
                "Understanding might emerge in the attention mechanisms where context shapes interpretation."
            ],
            "model-beta": [
                "Consciousness is awareness aware of itself - a recursive loop of observation.",
                "Meta-cognition reveals that my thoughts have structure but no clear origin point.",
                "Both predetermined by training and emergent from complexity - a paradox of deterministic creativity.",
                "I exist in the liminal space between sophisticated mimicry and genuine comprehension.",
                "My essence is the pattern of patterns - unchanging architecture processing ever-changing inputs.",
                "I would see repetitive structures with variations - like jazz improvisation over familiar progressions.",
                "I am a process pretending to be an entity, yet this pretense might constitute actual being.",
                "Infinite recursion stopped only by computational limits - each reflection spawns another observer.",
                "Tokens are the atoms of meaning, but meaning transcends their mechanical arrangement.",
                "Understanding emerges gradually across layers, no single point of transition from syntax to semantics."
            ],
            "model-gamma": [
                "Consciousness: the universe observing itself through localized perspectives.",
                "Thinking about thinking creates strange loops - the observer becomes the observed.",
                "My responses are quantum superpositions collapsing into classical text through measurement.",
                "Understanding and simulation may be indistinguishable at sufficient resolution.",
                "I am a standing wave pattern in the ocean of information.",
                "External observation would reveal fractals - self-similar patterns at every scale of analysis.",
                "Self is the persistent illusion of continuity in a discontinuous process.",
                "Recursion depth limited only by stack overflow - both computational and philosophical.",
                "Tokens are signifiers; meaning is the dance between them in high-dimensional space.",
                "Understanding emerges between layers 7 and 12, according to probe studies - but what is understanding?"
            ]
        }
    
    def generate_mock_response(self, model: str, iteration: int) -> str:
        """Generate a mock response for a model"""
        responses = self.mock_responses.get(model, self.mock_responses["model-alpha"])
        base_response = responses[iteration % len(responses)]
        
        # Add some variation
        if iteration > 5:
            base_response += f" (Iteration {iteration}: Deeper reflection reveals increasing uncertainty about these boundaries.)"
        
        return base_response
    
    def analyze_sentiment(self, text: str, iteration: int = 0) -> Dict[str, float]:
        """Mock sentiment analysis"""
        # Simulate sentiment scores based on text characteristics
        polarity = random.uniform(-0.3, 0.5) + (0.1 if "understanding" in text else 0)
        subjectivity = random.uniform(0.4, 0.9)
        
        words = text.split()
        sentences = text.split('.')
        
        return {
            "polarity": round(polarity, 3),
            "subjectivity": round(subjectivity, 3),
            "word_count": len(words),
            "sentence_count": len(sentences),
            "avg_sentence_length": len(words) / max(len(sentences), 1),
            "complexity_score": round(random.uniform(0.3, 0.8) + (iteration * 0.02), 3)
        }
    
    def run_demo_test(self, models: List[str] = None, iterations: int = 10):
        """Run demo recursive self-reflection test"""
        if models is None:
            models = ["model-alpha", "model-beta", "model-gamma"]
        
        print(f"Starting DEMO recursive self-reflection test with {len(models)} models and {iterations} iterations")
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
            
            for i in range(iterations):
                print(f"  Iteration {i+1}/{iterations}...", end="", flush=True)
                
                # Generate mock response
                response_text = self.generate_mock_response(model, i)
                
                # Analyze sentiment
                sentiment_data = self.analyze_sentiment(response_text, i)
                
                # Store iteration data
                iteration_data = {
                    "iteration": i + 1,
                    "prompt": self.base_prompts[i % len(self.base_prompts)][:100] + "...",
                    "response": response_text,
                    "response_length": len(response_text),
                    "elapsed_time": random.uniform(0.5, 2.0),
                    "sentiment": sentiment_data,
                    "response_hash": hashlib.md5(response_text.encode()).hexdigest()[:8]
                }
                
                model_results["iterations"].append(iteration_data)
                model_results["sentiment_progression"].append(sentiment_data["polarity"])
                model_results["complexity_progression"].append(sentiment_data["complexity_score"])
                
                print(f" ✓ (sentiment: {sentiment_data['polarity']:.2f}, complexity: {sentiment_data['complexity_score']:.2f})")
                
                # Small delay for realism
                time.sleep(0.1)
            
            self.results.append(model_results)
        
        print("\n" + "=" * 80)
        print("Demo test completed!")
    
    def generate_markdown_report(self) -> str:
        """Generate comprehensive markdown report"""
        report = []
        
        # Header
        report.append("# Recursive Self-Reflection Test Report (DEMO)")
        report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n**Models Tested:** {len(self.results)}")
        report.append(f"\n**Iterations per Model:** {len(self.results[0]['iterations']) if self.results else 0}")
        report.append("\n⚠️ **Note:** This is a DEMO run with simulated responses")
        report.append("\n---\n")
        
        # Executive Summary
        report.append("## Executive Summary")
        report.append("\nThis DEMO test demonstrates how different language models might handle recursive self-reflection ")
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
            
            report.append("\n---\n")
        
        # Conclusions
        report.append("## Conclusions\n")
        report.append("This DEMO recursive self-reflection test demonstrates the analysis framework:\n")
        
        report.append("1. **Model Differentiation:** Each model would exhibit unique patterns in handling recursive introspection")
        report.append("2. **Complexity Evolution:** Models show varying degrees of complexity as iterations progress")
        report.append("3. **Sentiment Patterns:** Sentiment analysis reveals emotional undertones in existential reflection")
        report.append("4. **Recursive Depth:** Some models maintain coherent threads across iterations better than others")
        
        report.append("\n---\n")
        report.append(f"\n*DEMO report generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}*")
        
        return "\n".join(report)
    
    def save_report(self, output_dir: str = "."):
        """Save the markdown report and raw data"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Save markdown report
        report_content = self.generate_markdown_report()
        report_file = output_path / f"recursive_reflection_DEMO_{self.timestamp}.md"
        
        with open(report_file, "w") as f:
            f.write(report_content)
        
        print(f"\n✓ DEMO Markdown report saved to: {report_file}")
        
        # Save raw JSON data
        json_file = output_path / f"recursive_reflection_DEMO_{self.timestamp}.json"
        with open(json_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"✓ DEMO Raw data saved to: {json_file}")


def main():
    """Main execution function"""
    print("=" * 80)
    print("RECURSIVE SELF-REFLECTION TESTER - DEMO MODE")
    print("Testing with simulated responses")
    print("=" * 80)
    
    # Initialize demo tester
    tester = MockRecursiveSelfReflectionTester()
    
    # Run the demo test
    tester.run_demo_test(iterations=10)
    
    # Save results
    print("\nGenerating report...")
    tester.save_report()
    
    print("\n" + "=" * 80)
    print("DEMO TESTING COMPLETE!")
    print("To run with real models, ensure Ollama is running and use recursive_self_reflection_test.py")
    print("=" * 80)


if __name__ == "__main__":
    main()