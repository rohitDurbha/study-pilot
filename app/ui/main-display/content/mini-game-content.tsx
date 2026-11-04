'use client';

import React, { useState } from 'react';

interface MiniGameChallenge {
  task: string;
  solution: string;
  uiType: string;
}

interface MiniGameContentProps {
  data: {
    title: string;
    challenges: MiniGameChallenge[];
  };
}

export default function MiniGameContent({ data }: MiniGameContentProps) {
  const [droppedTasks, setDroppedTasks] = useState<{ [key: string]: string }>({});
  const [draggingTask, setDraggingTask] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  // 🛡️ PROTECTION: If data is undefined or empty
  if (!data || !data.challenges || data.challenges.length === 0) {
    return (
      <div className="w-full p-8 text-center text-red-500">
        No mini-game challenges available.
      </div>
    );
  }

  const handleDragStart = (task: string) => {
    if (submitted) return;
    setDraggingTask(task);
  };

  const handleDrop = (solution: string) => {
    if (draggingTask) {
      setDroppedTasks(prev => ({
        ...prev,
        [solution]: draggingTask,
      }));
      setDraggingTask(null);
    }
  };

  const handleSubmit = () => {
    setSubmitted(true);
  };

  const handleReset = () => {
    setDroppedTasks({});
    setSubmitted(false);
  };

  const isAllDropped = Object.keys(droppedTasks).length === data.challenges.length;

  const calculateScore = () => {
    let score = 0;
    data.challenges.forEach((challenge) => {
      if (droppedTasks[challenge.solution] === challenge.task) {
        score += 1;
      }
    });
    return score;
  };

  return (
    <div className="w-full h-full max-w-4xl mx-auto p-6 flex flex-col gap-6 overflow-auto">
      <h1 className="text-2xl font-bold text-center">{data.title}</h1>

      <div className="flex flex-col md:flex-row gap-8 mt-8">
        {/* Draggables */}
        <div className="flex-1 bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg min-h-[200px]">
          <h2 className="font-semibold text-center mb-4">Tasks</h2>
          <div className="flex flex-wrap gap-3 justify-center">
            {data.challenges
              .filter(challenge => !Object.values(droppedTasks).includes(challenge.task))
              .map((challenge, idx) => (
                <div
                  key={idx}
                  draggable={!submitted}
                  onDragStart={() => handleDragStart(challenge.task)}
                  className={`p-3 bg-white dark:bg-gray-700 dark:text-gray-100 rounded-md shadow-md cursor-move text-center w-40 ${
                    submitted ? "opacity-50 cursor-default" : ""
                  }`}
                >
                  {challenge.task}
                </div>
              ))}
          </div>
        </div>

        {/* Droppables */}
        <div className="flex-1 bg-green-50 dark:bg-green-900/20 p-4 rounded-lg min-h-[200px]">
          <h2 className="font-semibold text-center mb-4">Solutions (Questions)</h2>
          <div className="flex flex-col gap-4">
            {data.challenges.map((challenge, idx) => {
              const userAnswer = droppedTasks[challenge.solution];
              const isCorrect = userAnswer === challenge.task;

              return (
                <div
                  key={idx}
                  onDragOver={e => e.preventDefault()}
                  onDrop={() => handleDrop(challenge.solution)}
                  className={`p-4 rounded-md min-h-[80px] flex flex-col items-center justify-start gap-2
                    ${submitted ? (isCorrect ? "bg-green-100 dark:bg-green-900/30 border border-green-400" : "bg-red-100 dark:bg-red-900/30 border border-red-400") : "bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600"}
                  `}
                >
                  {/* Always show the solution/question */}
                  <div className="text-sm font-semibold text-gray-700 dark:text-gray-200 text-center">
                    {challenge.solution}
                  </div>

                  {/* Below, show dropped answer */}
                  <div className="mt-2">
                    {userAnswer ? (
                      <div className="font-medium">{userAnswer}</div>
                    ) : (
                      <div className="text-gray-400 italic">Drop Answer Here</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Submit or Result */}
      <div className="flex justify-center mt-8">
        {!submitted ? (
          <button
            disabled={!isAllDropped}
            onClick={handleSubmit}
            className={`px-6 py-2 rounded-md font-semibold ${
              isAllDropped ? "bg-blue-600 hover:bg-blue-700 text-white" : "bg-gray-300 text-gray-500 cursor-not-allowed"
            }`}
          >
            Submit
          </button>
        ) : (
          <div className="text-center">
            <p className="text-2xl font-bold mb-4">
              You scored {calculateScore()} / {data.challenges.length}!
            </p>
            <button
              onClick={handleReset}
              className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-md font-semibold"
            >
              Play Again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
