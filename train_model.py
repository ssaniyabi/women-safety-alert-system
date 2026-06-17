import pickle
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

def train_safety_model():
    print("--- Step 1: Loading Dataset ---")
    try:
        df = pd.read_csv("dataset.csv")
        print(f"Dataset loaded successfully with {len(df)} rows.")
    except FileNotFoundError:
        print("Error: dataset.csv not found! Please run dataset_generator.py first.")
        return

    # Check distribution of categories
    print("\nClass distribution in dataset:")
    print(df["label_name"].value_counts())

    # Generate and save a simple class distribution plot for the project report
    print("\n--- Step 2: Generating Dataset Distribution Plot ---")
    plt.figure(figsize=(8, 5))
    counts = df["label_name"].value_counts()
    
    # Order colors properly based on index order
    color_map = {"Safe": "green", "Warning": "orange", "Emergency": "red"}
    bar_colors = [color_map[label] for label in counts.index]
    
    plt.bar(counts.index, counts.values, color=bar_colors, edgecolor="black", width=0.6)
    plt.title("Women Safety Dataset - Class Distribution", fontsize=14, fontweight="bold")
    plt.xlabel("Safety Category", fontsize=12)
    plt.ylabel("Number of Sentences", fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    for i, v in enumerate(counts.values):
        plt.text(i, v + 1, str(v), ha='center', fontweight='bold')
        
    plt.tight_layout()
    plt.savefig("dataset_distribution.png")
    print("Distribution plot saved as 'dataset_distribution.png'")
    plt.close()

    print("\n--- Step 3: Preparing Text Data ---")
    # Features (X) and Labels (y)
    X = df["text"]
    y = df["label"]

    # Split dataset into training and testing (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    print(f"Training set size: {len(X_train)} samples")
    print(f"Testing set size: {len(X_test)} samples")

    print("\n--- Step 4: Extracting Features using TF-IDF ---")
    # TF-IDF Vectorizer converts text into numerical features
    vectorizer = TfidfVectorizer(lowercase=True, stop_words="english")
    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)
    print("Text converted to numerical features using TF-IDF successfully.")

    print("\n--- Step 5: Training Logistic Regression Model ---")
    # Simple Logistic Regression classifier
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train_tfidf, y_train)
    print("Model training completed.")

    print("\n--- Step 6: Model Evaluation ---")
    # Make predictions on test data
    y_pred = model.predict(X_test_tfidf)

    # Calculate and display metrics
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model Accuracy on Test Data: {accuracy * 100:.2f}%")
    
    print("\nClassification Report:")
    target_names = ["Safe (0)", "Warning (1)", "Emergency (2)"]
    print(classification_report(y_test, y_pred, target_names=target_names))

    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    print("\n--- Step 7: Saving Model & Vectorizer ---")
    # Save the trained model and vectorizer using pickle
    with open("model.pkl", "wb") as f_model:
        pickle.dump(model, f_model)
    with open("vectorizer.pkl", "wb") as f_vec:
        pickle.dump(vectorizer, f_vec)
        
    print("Saved model as 'model.pkl'")
    print("Saved vectorizer as 'vectorizer.pkl'")
    print("\nTraining workflow completed successfully! You are ready to run app.py.")

if __name__ == "__main__":
    train_safety_model()
