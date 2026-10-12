/* ponytail: all brand glyphs self-hosted — no CDN, no broken images, works offline */

import trustVercel from '../assets/logos/trust-vercel.svg';
import trustStripe from '../assets/logos/trust-stripe.svg';
import trustLinear from '../assets/logos/trust-linear.svg';
import trustNotion from '../assets/logos/trust-notion.svg';
import trustFigma from '../assets/logos/trust-figma.svg';
import trustSupabase from '../assets/logos/trust-supabase.svg';
import trustRailway from '../assets/logos/trust-railway.svg';
import trustResend from '../assets/logos/trust-resend.svg';
import trustLoops from '../assets/logos/trust-loops.svg';
import trustCaldotcom from '../assets/logos/trust-caldotcom.svg';

import anthropic from '../assets/logos/anthropic.svg';
import googlegemini from '../assets/logos/googlegemini.svg';
import mistralai from '../assets/logos/mistralai.svg';
import googlecloud from '../assets/logos/googlecloud.svg';
import huggingface from '../assets/logos/huggingface.svg';
import ollama from '../assets/logos/ollama.svg';
import mercury from '../assets/logos/mercury.png';

import openai from '../assets/logos/openai.svg';
import groq from '../assets/logos/groq.svg';
import aws from '../assets/logos/aws.svg';
import azure from '../assets/logos/azure.svg';

/** Gray glyphs for the trusted-by row (keyed by simple-icons slug). */
export const trustLogo: Record<string, string> = {
  vercel: trustVercel, stripe: trustStripe, linear: trustLinear,
  notion: trustNotion, figma: trustFigma, supabase: trustSupabase,
  railway: trustRailway, resend: trustResend, loops: trustLoops,
  caldotcom: trustCaldotcom,
};

/** White glyphs for dark cards (keyed by integration/provider key). */
export const brandLogo: Record<string, string> = {
  anthropic, googlegemini, mistralai, googlecloud, huggingface, ollama,
  openai, groq, aws, azure, mercury,
};

/** Wikimedia wordmarks ship dark — CSS filter flips them white (see .logo-white). */
export const filteredLogo = new Set(['openai', 'groq', 'aws', 'azure']);

/** Wide lockups need width-capped sizing instead of a square box. */
export const wideLogo = new Set(['openai', 'groq', 'aws', 'azure', 'caldotcom']);
