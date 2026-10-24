import { expect, test } from 'vitest';
import { sceneProgress, sceneStep } from './scrollMotion';

test('scene progress clamps before/after the held scene and handles a non-scrollable stage', () => {
  expect(sceneProgress(100, 2400, 800)).toBe(0);
  expect(sceneProgress(-800, 2400, 800)).toBe(.5);
  expect(sceneProgress(-3000, 2400, 800)).toBe(1);
  expect(sceneProgress(-50, 500, 800)).toBe(0);
});

test('scroll selection advances and reverses through all steps at bounded progress', () => {
  expect([0, .34, .67, .5, .1, 1].map(progress => sceneStep(progress, 3))).toEqual([0, 1, 2, 1, 0, 2]);
});
