import { motion } from 'framer-motion';

const SonaEyeGraph = () => {
  // Path Definitions: Relaxed (Default) vs Tense state
  // Relaxed: Center is higher, closer to a circle (y: 10) - gathering inward
  // Tense: Center is flatter, spreading outward (y: 50) - expanding outward
  // Control points adjusted to be closer to center for a circular shape
  const bellCurveRelaxed = 'M 0 100 C 60 100, 70 10, 100 10 S 140 100, 200 100';
  const bellCurveTense = 'M 0 100 C 60 100, 70 50, 100 50 S 140 100, 200 100';

  // Animation Variables
  // Card appearance delay: 1.3
  const cardAppearDelay = 1.1;
  const breathingDuration = 9.9; // Breathing cycle (seconds) — repeat animation speed

  // Animation settings for each path
  const getPathAnimation = (index: number) => {
    const initialDelay = cardAppearDelay + index * 0.1;
    const breathingStartDelay = cardAppearDelay + 2; // Start after initial appearance

    return {
      // Initial appearance animation
      pathLength: [0, 1],
      opacity: [0, 0.8],
      // Breathing animation
      d: [bellCurveRelaxed, bellCurveTense, bellCurveRelaxed],
      strokeWidth: [1, 2.5, 1],
      filter: ['url(#glow-weak)', 'url(#glow-strong)', 'url(#glow-weak)'],
      transition: {
        // Initial appearance transition
        pathLength: {
          duration: 2,
          ease: 'easeInOut' as const,
          delay: initialDelay,
        },
        opacity: {
          duration: 1.5,
          delay: initialDelay,
        },
        // Breathing transition (starts after initial appearance)
        d: {
          duration: breathingDuration,
          repeat: Infinity,
          ease: 'easeInOut' as const,
          repeatType: 'reverse' as const,
          delay: breathingStartDelay,
        },
        strokeWidth: {
          duration: breathingDuration,
          repeat: Infinity,
          ease: 'easeInOut' as const,
          repeatType: 'reverse' as const,
          delay: breathingStartDelay,
        },
        filter: {
          duration: breathingDuration,
          repeat: Infinity,
          ease: 'easeInOut' as const,
          repeatType: 'reverse' as const,
          delay: breathingStartDelay,
        },
      },
    };
  };

  return (
    <div className="relative w-full h-full flex items-center justify-center">
      <svg viewBox="0 0 200 200" className="w-full h-full overflow-visible">
        <defs>
          {/* Gradient: Transparent ends to make line fade out naturally */}
          <linearGradient id="eyeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3B82F6" stopOpacity="0" />
            <stop offset="40%" stopColor="#8B5CF6" stopOpacity="0.8" />
            <stop offset="50%" stopColor="#FDE68A" stopOpacity="1" />{' '}
            {/* Center is slightly yellow */}
            <stop offset="60%" stopColor="#EF4444" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#EF4444" stopOpacity="0" />
          </linearGradient>

          {/* Glow Filters */}
          <filter id="glow-weak" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-strong" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* --- Rotating Curves Group --- */}
        <g className="mix-blend-screen">
          {/* 1. Horizontal Curve (The Upper Eyelid) - Inverted to be convex up */}
          {/* rotate(0) is convex down, so we use it as is? No, SVG coords y increases downwards. */}
          {/* 0,100 -> 100,20 (moves up) -> This itself is 'mountain' shape */}
          <motion.path
            fill="none"
            stroke="url(#eyeGradient)"
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0, d: bellCurveRelaxed }}
            animate={getPathAnimation(0)}
            // Upper eyelid (default mountain shape)
          />

          {/* 2. Horizontal Curve (The Lower Eyelid) */}
          {/* 180 deg rotation = convex down (valley) */}
          <motion.path
            fill="none"
            stroke="url(#eyeGradient)"
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0, d: bellCurveRelaxed }}
            animate={getPathAnimation(1)}
            transform="rotate(180 100 100)"
          />

          {/* 3. Vertical Curve (Left) */}
          {/* 90 deg rotation */}
          <motion.path
            fill="none"
            stroke="url(#eyeGradient)"
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0, d: bellCurveRelaxed }}
            animate={getPathAnimation(2)}
            transform="rotate(90 100 100)"
            className="opacity-60" // Vertical lines are slightly fainter
          />

          {/* 4. Vertical Curve (Right) */}
          {/* 270 deg rotation */}
          <motion.path
            fill="none"
            stroke="url(#eyeGradient)"
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0, d: bellCurveRelaxed }}
            animate={getPathAnimation(3)}
            transform="rotate(270 100 100)"
            className="opacity-60"
          />
        </g>
      </svg>
    </div>
  );
};

export default SonaEyeGraph;
