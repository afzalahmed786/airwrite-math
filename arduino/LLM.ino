#include "model_1.h"
#include "secrets.h"
#include <tflm_esp32.h>
#include <eloquent_tinyml.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>


#define ARENA_SIZE 60000  // Adjust based on your model's requirements
#define NUM_TIME_STEPS 30
#define NUM_FEATURES 6   // 3 for accelerometer, 3 for gyroscope
#define NUM_INPUTS (NUM_TIME_STEPS * NUM_FEATURES)
#define NUM_OUTPUTS 7 // 0-4 digits and '+'

#define NUMBER_OF_OPS 50


// Arrays to store questions and answers
String questions[5];
String answers[5];
int difficultyLevel = 0; // Start with basic difficulty
int correctStreak = 0;   // Track consecutive correct answers


const char* labels[NUM_OUTPUTS] = { "0", "1", "2", "3","4", "!","$"};
String x[100];
int i=0;


Eloquent::TF::Sequential<NUMBER_OF_OPS, ARENA_SIZE> tf;
Adafruit_MPU6050 mpu;

const int buttonPin = 2;



void configureIMU() {
    delay(10);
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_5_HZ);
}

bool readIMUData(float data[NUM_TIME_STEPS][NUM_FEATURES], int& actualSteps) {
    actualSteps = 0;
    while (digitalRead(buttonPin) == HIGH && actualSteps < NUM_TIME_STEPS) {
        sensors_event_t a, g, temp;
        mpu.getEvent(&a, &g, &temp);
        
        data[actualSteps][0] = a.acceleration.x;
        data[actualSteps][1] = a.acceleration.y;
        data[actualSteps][2] = a.acceleration.z;
        data[actualSteps][3] = g.gyro.x;
        data[actualSteps][4] = g.gyro.y;
        data[actualSteps][5] = g.gyro.z;
        
        //  Serial.printf("Step %d: %.2f, %.2f, %.2f, %.2f, %.2f, %.2f\n",
        //                actualSteps,
        //              data[actualSteps][0], data[actualSteps][1], data[actualSteps][2],
        //               data[actualSteps][3], data[actualSteps][4], data[actualSteps][5]);
        actualSteps++;
        delay(100);  // 100Hz sampling rate
    }
    return actualSteps > 0;
}

void padData(float source[NUM_TIME_STEPS][NUM_FEATURES], int actualSteps, float destination[NUM_TIME_STEPS][NUM_FEATURES]) {
    // Copy actual data
    for (int i = 0; i < min(actualSteps, NUM_TIME_STEPS); i++) {
        for (int j = 0; j < NUM_FEATURES; j++) {
            destination[i][j] = source[i][j];
        }
    }
    
    // Pad with zeros if necessary
    for (int i = actualSteps; i < NUM_TIME_STEPS; i++) {
        for (int j = 0; j < NUM_FEATURES; j++) {
            destination[i][j] = 0.0f;
        }
    }
    
    // If we have more data than needed, print a warning
    if (actualSteps > NUM_TIME_STEPS) {
        Serial.printf("Warning: Gesture too long. Using first %d steps out of %d.\n", NUM_TIME_STEPS, actualSteps);
    }
}

String runInference(float imu_data[NUM_TIME_STEPS][NUM_FEATURES]) {
    float input_data[NUM_INPUTS];
    for (int i = 0; i < NUM_TIME_STEPS; i++) {
        for (int j = 0; j < NUM_FEATURES; j++) {
            input_data[i * NUM_FEATURES + j] = imu_data[i][j];
        }
    }
  
    if (tf.predict(input_data).isOk()) {
        int predicted_class = tf.classification;
        float* out = tf.outputs; // Access the output array
        
        if (out[predicted_class] > 0.60) {
            x[i] = labels[predicted_class];   
            return x[i];
        } else {
            return "-1";
        }
    } 
}

void wifisetup(){
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  while (!Serial);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to ");
  Serial.println(ssid);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(".");
  }
  Serial.println("connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

}

void generateQuestions() {
  HTTPClient http;
  String url = String(flaskServer) + "/generate_questions?difficulty=" + String(difficultyLevel);
  if (http.begin(url)) {
    int httpCode = http.GET();

    if (httpCode == HTTP_CODE_OK) {
      String payload = http.getString();
      DynamicJsonDocument doc(1024);
      deserializeJson(doc, payload);

      // Extract questions from the response
      for (int i = 0; i < 5; i++) {
        questions[i] = doc["questions"][i].as<String>();
      }
    } else {
      Serial.printf("HTTP GET failed, error: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  } else {
    Serial.println("Unable to connect to Flask server");
  }
}

void evaluateTest() {
  HTTPClient http;
  String url = String(flaskServer) + "/evaluate_answers";

  // Create JSON payload with answers, questions, and difficulty
  DynamicJsonDocument doc(1024);

// Create JSON arrays
JsonArray answersArray = doc.createNestedArray("answers");

// Add values to the arrays
for (int i = 0; i < 5; i++) {
    answersArray.add(String(answers[i]));       // Ensure answers are strings
}

// Add difficulty level
doc["difficulty"] = difficultyLevel;
JsonArray questionsArray = doc.createNestedArray("questions");
for (int i = 0; i < 5; i++) {
    questionsArray.add(String(questions[i]));   // Ensure questions are strings
}



  // Serialize JSON to a string
  String payload;
  serializeJson(doc, payload);
  // Serial.println(payload);


  // Send POST request
  if (http.begin(url)) {
    http.addHeader("Content-Type", "application/json");
    int httpCode = http.POST(payload);

    if (httpCode == HTTP_CODE_OK) {
      String response = http.getString();

      // Parse the response
      DynamicJsonDocument resDoc(1024);
      DeserializationError error = deserializeJson(resDoc, response);

      if (error) {
        Serial.printf("Failed to parse JSON response: %s\n", error.c_str());
      } else {
        // Extract data from the response
        int correctCount = 0;
        int suggestedDifficulty = difficultyLevel; // Parse suggested difficulty
        String message = resDoc["message"]; // Parse message
        // Display detailed feedback for each question
        JsonArray evaluations = resDoc["evaluations"];
        for (int i = 0; i < evaluations.size(); i++) {
          JsonObject evaluation = evaluations[i];
          String question = evaluation["question"];
          String userAnswer = evaluation["user_answer"];
          String correctAnswer = evaluation["correct_answer"];

          Serial.println("");
          Serial.print("Question ");
          Serial.print(i + 1);
          Serial.print(": ");
          Serial.println (question);
          Serial.print("  Your Answer: ");
          Serial.println(userAnswer);
          Serial.print("  Correct Answer: ");
          Serial.println(correctAnswer);
          Serial.print("  Result: ");
          if (userAnswer == correctAnswer){
            Serial.println("Correct");
            correctCount++;        
          } else Serial.println("Incorrect");   
        }
        
        if (correctCount >= 3){
            suggestedDifficulty = difficultyLevel + 1;
        }else if (correctCount >= 2){
            suggestedDifficulty = difficultyLevel ;
        }else {
            suggestedDifficulty = (difficultyLevel > 0) ? (difficultyLevel - 1) : 0;
        }

        if(suggestedDifficulty > difficultyLevel){
          Serial.println("We suggest you upgrade to Level: " + String(suggestedDifficulty) + " Enter 1 to upgrade,Enter 0 to remain at the same Level");
        }
        else if(suggestedDifficulty < difficultyLevel){
          Serial.println("We suggest you move to a easier level of " + String(suggestedDifficulty) + " Enter 1 to move down ,Enter 0 to try again at the same Level");
        } else {
          Serial.println("We suggest you try again  at this level one more time");
        }

        if(suggestedDifficulty != difficultyLevel)
        {
        while (digitalRead(buttonPin) == LOW); // Wait for button press

        float raw_imu_data[NUM_TIME_STEPS][NUM_FEATURES];
        float padded_imu_data[NUM_TIME_STEPS][NUM_FEATURES];
        int actualSteps;
        readIMUData(raw_imu_data, actualSteps);
        padData(raw_imu_data, actualSteps, padded_imu_data);
        String digit = runInference(padded_imu_data);

        // Convert digit to integer
        int userChoice = digit.toInt(); // Convert string to int

        // Debug: Print the user choice
        Serial.print("User choice: ");
        Serial.println(userChoice);

        // Update difficulty level based on user choice
        if (userChoice == 1) {
          difficultyLevel = suggestedDifficulty; // Change to suggested difficulty
          Serial.println("Difficulty level changed to: " + String(difficultyLevel));
        } else {
          Serial.println("Staying at current difficulty level: " + String(difficultyLevel));
        }
        }
      }
    } else {
      Serial.printf("HTTP POST failed, error: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  } else {
    Serial.println("Unable to connect to Flask server");
  }
}

void setup() {
   Serial.begin(115200);
    Serial.println("CNN HANDWRITING RECOGNITION");
    pinMode(buttonPin, INPUT_PULLUP);

    if (!mpu.begin()) {
        while (1) delay(10);
    }
    configureIMU();
    tf.setNumInputs(NUM_INPUTS);
    tf.setNumOutputs(NUM_OUTPUTS);
    // Register operations
    tf.resolver.AddAdd();
    tf.resolver.AddConv2D();
    tf.resolver.AddDequantize();
    tf.resolver.AddQuantize();
    tf.resolver.AddExpandDims();
    tf.resolver.AddReshape();
    tf.resolver.AddMaxPool2D();
    tf.resolver.AddFullyConnected();
    tf.resolver.AddSoftmax();
    tf.resolver.AddMul();
    tf.resolver.AddMean();

    while (!tf.begin(tfModel).isOk()) {
        Serial.println(tf.exception.toString());
        delay(3000);
    }
    registerNetworkOps(tf);
    wifisetup();

    Serial.println("What difficulty do you want to start on?");


    bool flag = true;
    while(flag){
      while (digitalRead(buttonPin) == LOW);
      float raw_imu_data[NUM_TIME_STEPS][NUM_FEATURES];
      float padded_imu_data[NUM_TIME_STEPS][NUM_FEATURES];
      int actualSteps;
      if (readIMUData(raw_imu_data, actualSteps)) {
      padData(raw_imu_data, actualSteps, padded_imu_data);
      String digit = runInference(padded_imu_data);
      int userChoice = digit.toInt();
      if (digit == "$")
      {
        Serial.print("You have exited the program.");
        while(1);
      }
      else if (digit == "!") {
          difficultyLevel = 0;
          Serial.println("Difficulty Level: 0");
          flag = false;
      } else if (digit != "-1") {
          difficultyLevel = userChoice;
          Serial.println("Difficulty Level: " + digit);
          flag = false;
      } else {
          Serial.println("Invalid gesture. Try again.");
      }
    }
  }
  generateQuestions();
}

void loop() {
    for (int i = 0; i < 5; i++) {
    String number = "";
    bool readingDigits = true;
    unsigned long startTime = millis();
    Serial.println("");
    Serial.print("Question ");
    Serial.print(i + 1);
    Serial.println(": ");
    Serial.println(questions[i]);

    while (readingDigits) {
        while (digitalRead(buttonPin) == LOW);
        float raw_imu_data[NUM_TIME_STEPS][NUM_FEATURES];
        float padded_imu_data[NUM_TIME_STEPS][NUM_FEATURES];
        int actualSteps;
        if (readIMUData(raw_imu_data, actualSteps)) {
            padData(raw_imu_data, actualSteps, padded_imu_data);
            String digit = runInference(padded_imu_data);
             if (digit == "$")
             {
                Serial.print("You have exited the program.");
                while(1);
             }
            else if (digit == "!") {
                if (number.length() > 0) {
                    readingDigits = false; 
                } else {
                    number = "";
                    readingDigits = false;
                }
            } else if (digit != "-1") {
                number += digit; // Append the digit to the number
                Serial.print("Current number: ");
                Serial.println(number);
            } else {
                Serial.println("Invalid gesture. Try again.");
            }
        } else {
            Serial.println("Failed to read IMU data. Retrying...");
        }
    }
    answers[i] = number;
    Serial.println("");
    Serial.print("Your answer: ");
    Serial.println(answers[i]);
  }
    evaluateTest();
    generateQuestions();
}
   
