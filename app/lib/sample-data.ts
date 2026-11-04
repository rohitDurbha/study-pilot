export const SAMPLE_TEXT_DATA = {
  "data": {
      "content": "## Operating Systems: An Overview\n\n### What is an Operating System?\n\n* A program acting as an intermediary between the user and computer hardware.\n* **Goals:**\n    * Execute user programs and simplify problem-solving.\n    * Make the computer system user-friendly.\n    * Utilize computer hardware efficiently.\n\n\n### Computer System Structure\n\nA computer system comprises four key components:\n\n* **Hardware:** Provides the fundamental computing resources.\n    * CPU\n    * Memory\n    * I/O devices\n* **Operating System:**  Manages and coordinates hardware usage across applications and users.\n* **Application Programs:** Define how system resources are used to solve user problems. Examples include:\n    * Word processors\n    * Compilers\n    * Web browsers\n    * Database systems\n    * Video games\n* **Users:** The individuals, machines, or other computers interacting with the system.\n\n\n### What Operating Systems Do\n\nThe role of an operating system depends on the perspective:\n\n* **User Perspective:**\n    * Focus on convenience, ease of use, and performance.\n    * Generally unconcerned with resource utilization.\n* **Shared Computer Systems (Mainframes/Minicomputers):**\n    * Must balance the needs of all users.\n* **Dedicated Systems (Workstations):**\n    * Users have dedicated resources but often utilize shared resources from servers.\n* **Handheld Computers:**\n    * Resource-constrained, prioritizing usability and battery life.\n* **Embedded Computers (Devices/Automobiles):**\n    * May have minimal or no user interface.",
      "title": "OS"
  },
  "id": "text-d945661d-1783-4f9d-992f-d0921fa1fcbb",
  "type": "text"
};


export const SAMPLE_MIND_MAP_DATA = 
{
  "data": {
    "root": {
      "children": [
        {
          "children": [
            {
              "title": "Execute User Programs"
            },
            {
              "title": "Enhance User Experience"
            },
            {
              "title": "Efficient Resource Management"
            }
          ],
          "title": "What is an OS?"
        },
        {
          "children": [
            {
              "title": "Hardware"
            },
            {
              "title": "Operating System (OS)"
            },
            {
              "title": "Application Programs"
            },
            {
              "title": "Users"
            }
          ],
          "title": "Computer System Structure"
        },
        {
          "children": [
            {
              "children": [
                {
                  "title": "Convenience & Ease of Use"
                },
                {
                  "title": "Good Performance"
                },
                {
                  "title": "Shared Systems (e.g., Mainframes, Minicomputers)"
                },
                {
                  "title": "Dedicated Systems (e.g., Workstations)"
                },
                {
                  "title": "Handheld Devices (Usability & Battery Life)"
                }
              ],
              "title": "User Perspective"
            },
            {
              "children": [
                {
                  "children": [
                    {
                      "title": "Memory Management"
                    },
                    {
                      "title": "Process Scheduling"
                    },
                    {
                      "title": "I/O Operations"
                    },
                    {
                      "title": "Security"
                    }
                  ],
                  "title": "Resource Management"
                }
              ],
              "title": "System Perspective"
            },
            {
              "children": [
                {
                  "title": "Minimal/No User Interface"
                },
                {
                  "title": "Specialized & Optimized"
                }
              ],
              "title": "Embedded Systems"
            }
          ],
          "title": "What Operating Systems Do"
        }
      ],
      "title": "Operating Systems (OS)"
    },
    "title": "Operating Systems"
  },
  "id": "operating-systems-mindmap",
  "type": "mindmap"
}


export const SAMPLE_FLIP_CARD_DATA = {
  "data": {
    "cards": [
      {
        "back": "A program that acts as an intermediary between a user and the computer hardware. Its primary goals are to execute user programs, enhance convenience, and ensure efficient hardware utilization.",
        "front": "What is an Operating System?",
        "id": "1"
      },
      {
        "back": "Hardware, Operating System, Application Programs, and Users.",
        "front": "Name the four key components of a computer system.",
        "id": "2"
      },
      {
        "back": "Execute user programs, enhance user convenience, and ensure efficient hardware utilization.",
        "front": "What are the three main goals of an Operating System?",
        "id": "3"
      },
      {
        "back": "Convenience, ease of use, and good performance.",
        "front": "From a user perspective, what is the primary focus regarding an operating system?",
        "id": "4"
      },
      {
        "back": "A computer system integrated into other devices to perform dedicated functions, often with minimal or no user interface.",
        "front": "What is an embedded system?",
        "id": "5"
      },
      {
        "back": "A workstation is a powerful desktop computer designed for individual use, while a server provides resources or services to other computers over a network.",
        "front": "What is the difference between a workstation and a server?",
        "id": "6"
      },
      {
        "back": "To balance the needs of all users and ensure fair access and allocation of resources like CPU time, memory, and I/O devices.",
        "front": "Why is resource management a key concern for shared computer systems?",
        "id": "7"
      }
    ],
    "title": "Generated Flashcards"
  },
  "id": "flashcard-6438d5c3-ea9f-4638-9320-f7971b4a4fd2",
  "type": "flipcard"
};

export const SAMPLE_QUIZ_DATA = {
  "data": {
    "description": "Quiz to test your understanding!",
    "questions": [
      {
        "correctOptionIndex": 2,
        "explanation": "An OS manages the computer's hardware and software resources, bridging the gap between the user and the underlying machine.",
        "id": "q1",
        "options": [
          "To store and retrieve user data",
          "To develop application programs",
          "To act as an intermediary between the user and hardware",
          "To provide network connectivity"
        ],
        "question": "What is the primary role of an operating system (OS)?"
      },
      {
        "correctOptionIndex": 3,
        "explanation": "While an internet connection can be used by a computer system, it isn't a core component like the hardware, OS, and software that make up the system itself.",
        "id": "q2",
        "options": [
          "Hardware",
          "Operating System",
          "Application Programs",
          "Internet Connection"
        ],
        "question": "Which of the following is NOT a core component of a computer system?"
      },
      {
        "correctOptionIndex": 3,
        "explanation": "Users primarily focus on how easy and efficient the system is to use. Resource management is typically handled by the OS behind the scenes.",
        "id": "q3",
        "options": [
          "Ease of use",
          "Good performance",
          "Convenient interface",
          "Efficient resource utilization"
        ],
        "question": "From a user's perspective, what is the LEAST important aspect of an operating system?"
      },
      {
        "correctOptionIndex": 2,
        "explanation": "Due to their limited resources, handheld devices prioritize a user-friendly experience and long battery life.",
        "id": "q4",
        "options": [
          "High processing power",
          "Extensive storage capacity",
          "Usability and battery life",
          "Support for multiple users"
        ],
        "question": "What is the main focus of an operating system in handheld computers?"
      },
      {
        "correctOptionIndex": 2,
        "explanation": "Embedded systems are designed for specific control tasks within other devices and often operate without direct user interaction.",
        "id": "q5",
        "options": [
          "Workstations",
          "Servers",
          "Embedded Systems",
          "Handheld Computers"
        ],
        "question": "Which type of system typically has minimal or no user interface?"
      },
      {
        "correctOptionIndex": 1,
        "explanation": "The core difference is their purpose: workstations are designed for individual users performing complex tasks, while servers share resources across a network.",
        "id": "q6",
        "options": [
          "Workstations are more powerful than servers.",
          "Servers provide resources to other computers, while workstations are primarily for individual use.",
          "Workstations run different operating systems than servers.",
          "Servers have a graphical user interface, while workstations do not."
        ],
        "question": "What is the primary difference between workstations and servers?"
      },
      {
        "correctOptionIndex": 2,
        "explanation": "In a shared environment, the OS must manage resources effectively and ensure fair access for all users.",
        "id": "q7",
        "options": [
          "Prioritizing a single user's tasks",
          "Maximizing the performance of a specific application",
          "Balancing the needs of multiple users and ensuring fair resource allocation",
          "Minimizing power consumption"
        ],
        "question": "What is a key responsibility of an OS in shared computer systems (like mainframes)?"
      }
    ],
    "title": "Generated Quiz"
  },
  "id": "quiz-93d42cdb-86b3-4b84-969d-ab076fe3786d",
  "type": "quiz"
};


export const SAMPLE_MINI_GAME = {
  "data": {
    "challenges": [
      {
        "solution": "Acts as an intermediary between the user and the computer hardware.",
        "task": "Operating System",
        "uiType": "drag-drop"
      },
      {
        "solution": "The physical components of a computer system (CPU, memory, I/O devices).",
        "task": "Hardware",
        "uiType": "drag-drop"
      },
      {
        "solution": "Software that utilizes system resources to solve user problems.",
        "task": "Application Programs",
        "uiType": "drag-drop"
      },
      {
        "solution": "Focuses on ease of use, good performance, and convenience.",
        "task": "User Perspective (OS)",
        "uiType": "drag-drop"
      },
      {
        "solution": "Emphasizes efficient and fair resource management.",
        "task": "System Perspective (OS)",
        "uiType": "drag-drop"
      }
    ],
    "title": "Operating System Fundamentals"
  },
  "id": "os-fundamentals-drag-drop",
  "type": "mini-game"
};