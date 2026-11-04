import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { SAMPLE_FLIP_CARD_DATA } from '@/app/lib/sample-data';

interface FlipCardData {
  id: string;
  front: string;
  back: string;
}

interface FlipCardContentProps {
  data?: {
    title?: string;
    cards?: FlipCardData[];
  };
}

export default function FlipCardContent({
  data = SAMPLE_FLIP_CARD_DATA.data,
}: FlipCardContentProps): React.ReactElement {
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  const { title = 'Flip Cards', cards = [] } = data;

  const handleFlip = () => {
    setIsFlipped(!isFlipped);
  };

  const handleNext = () => {
    if (currentCardIndex < cards.length - 1) {
      setIsFlipped(false);
      setCurrentCardIndex(currentCardIndex + 1);
    }
  };

  const handlePrevious = () => {
    if (currentCardIndex > 0) {
      setIsFlipped(false);
      setCurrentCardIndex(currentCardIndex - 1);
    }
  };

  if (!cards || cards.length === 0) {
    return (
      <div className="text-center text-gray-500">No flash cards available</div>
    );
  }

  const currentCard = cards[currentCardIndex];

  return (
    <div className="w-full max-w-3xl mx-auto flex flex-col items-center">
      <h2 className="text-xl font-bold mb-6">{title}</h2>

      <div className="relative w-full h-80 perspective-1000 mb-6">
        <motion.div
          className="w-full h-full cursor-pointer"
          onClick={handleFlip}
          initial={false}
          animate={{
            rotateY: isFlipped ? 180 : 0,
          }}
          transition={{
            type: 'tween',
            ease: 'easeInOut',
            duration: 0.3,
            // stiffness: 300,
            // damping: 20,
          }}
          style={{
            transformStyle: 'preserve-3d',
            width: '100%',
            height: '100%',
            position: 'relative',
          }}
        >
          {/* Front of card */}
          <motion.div
            className="absolute w-full h-full bg-white dark:bg-gray-800 border-2 border-blue-400 dark:border-blue-600 rounded-lg p-6 flex items-center justify-center text-center"
            style={{
              backfaceVisibility: 'hidden',
              WebkitBackfaceVisibility: 'hidden',
              position: 'absolute',
              width: '100%',
              height: '100%',
            }}
          >
            <p className="text-2xl font-medium dark:text-gray-100">{currentCard.front}</p>
          </motion.div>

          {/* Back of card */}
          <motion.div
            className="absolute w-full h-full bg-blue-100 dark:bg-blue-900/40 border-2 border-blue-400 dark:border-blue-600 rounded-lg p-6 flex items-center justify-center text-center"
            style={{
              backfaceVisibility: 'hidden',
              WebkitBackfaceVisibility: 'hidden',
              transform: 'rotateY(180deg)',
              position: 'absolute',
              width: '100%',
              height: '100%',
            }}
          >
            <p className="text-2xl font-medium dark:text-gray-100">{currentCard.back}</p>
          </motion.div>
        </motion.div>
      </div>

      <div className="flex justify-between w-full">
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrevious}
            disabled={currentCardIndex === 0}
            className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <button
            onClick={handleNext}
            disabled={currentCardIndex === cards.length - 1}
            className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
        <div className="text-gray-600">
          Card {currentCardIndex + 1} of {cards.length}
        </div>
      </div>
    </div>
  );
}
