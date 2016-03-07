/** @file
* This file add support for Amlogic video decoding to enigma2
* Copyright (C) 2015  Christian Ege <k4230r6@gmail.com>
*
* This file is part of Enigma2
*
* AMLDecocder is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 2 of the License, or
* (at your option) any later version.
*
* AMLDecocder is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with AMLDecocder.  If not, see <http://www.gnu.org/licenses/>.
*/

// Modul includes
#include <lib/dvb/amldecoder.h>
// Project includes

#include <lib/base/cfile.h>
#include <lib/base/ebase.h>
#include <lib/base/eerror.h>
#include <lib/base/wrappers.h>
#include <lib/components/tuxtxtapp.h>

// Kernel includes
#include <linux/dvb/audio.h>
#include <linux/dvb/video.h>
#include <linux/dvb/dmx.h>

// System includes
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>

#include <pthread.h>


extern "C" {
#include <dvbcsa/dvbcsa.h>
}

#define TRACE__ eDebug("%s(%d): ",__PRETTY_FUNCTION__,__LINE__);


#define PVR_P0                _IO('o', 100)
#define PVR_P1                _IO('o', 101)
#define PVR_P2                _IO('o', 102)
#define PVR_P3                _IO('o', 103)
#define PVR_P4                _IOR('o', 104, int)


static void signal_handler(int x)
{
	TRACE__;
}

DEFINE_REF(eAMLTSMPEGDecoder);


eAMLTSMPEGDecoder::eAMLTSMPEGDecoder(eDVBDemux *demux, int decoder)
: m_demux(demux),
m_vpid(-1), m_vtype(-1), m_apid(-1), m_atype(-1), m_pcrpid(-1), m_textpid(-1),
m_width(-1), m_height(-1), m_framerate(-1), m_aspect(-1), m_progressive(-1),		
m_changed(0), m_decoder(decoder), m_radio_pic_on(0), m_video_clip_fd(-1), 
aml_fd(-1), cntl_fd(-1), m_showSinglePicTimer(eTimer::create(eApp)), m_VideoRead(eTimer::create(eApp))
{
	TRACE__
	if (m_demux)
	{
		m_demux->connectEvent(slot(*this, &eAMLTSMPEGDecoder::demux_event), m_demux_event_conn);
	}
	memset(&m_codec, 0, sizeof(codec_para_t ));
	memset(&am_sysinfo, 0, sizeof(dec_sysinfo_t));
	memset(&am_param, 0, sizeof(arm_audio_info));
	m_codec.handle = -1;
	
	CONNECT(m_showSinglePicTimer->timeout, eAMLTSMPEGDecoder::finishShowSinglePic);
	CONNECT(m_VideoRead->timeout, eAMLTSMPEGDecoder::parseVideoInfo);
	m_VideoRead->start(500, false);
	
	m_state = stateStop;
	adec_handle = NULL;
	
	if (m_demux && m_decoder == 0)	// Tuxtxt caching actions only on primary decoder
	eTuxtxtApp::getInstance()->initCache();
	
	cntl_fd = ::open("/dev/amvideo",  O_RDWR);
}

eAMLTSMPEGDecoder::~eAMLTSMPEGDecoder()
{
	TRACE__
	if (m_radio_pic_on)
	finishShowSinglePic();
	
	if (m_state == statePause) {

		if (adec_handle)
			audio_decode_resume(adec_handle);
		
		if ((m_vpid >= 0) && (m_vpid < 0x1FFF) && aml_fd >= 0)	 
			::ioctl(aml_fd, AMSTREAM_IOC_VPAUSE, 0);
		
		if (m_demux && m_demux->m_pvr_fd >= 0)
			::ioctl(m_demux->m_pvr_fd, PVR_P3);
	}
	m_vpid = m_apid = m_pcrpid = m_textpid = pidNone;
	m_changed = -1;
	setState();

	if (m_demux && m_decoder == 0)	// Tuxtxt caching actions only on primary decoder
	eTuxtxtApp::getInstance()->freeCache();

	if (adec_handle)
	{
		audio_decode_stop(adec_handle);
		audio_decode_release(&adec_handle);
	}
	adec_handle = NULL;
	if (aml_fd >= 0)
	close(aml_fd);
	
	if (cntl_fd >= 0)
	close(cntl_fd);
	setAvsyncEnable(0);
}


int eAMLTSMPEGDecoder::setState()
{
	TRACE__
	int res = 0;
	eDebug("%s() vpid=%d, apid=%d",__PRETTY_FUNCTION__, m_vpid, m_apid);
	return res;
}

int eAMLTSMPEGDecoder::m_pcm_delay=-1,
eAMLTSMPEGDecoder::m_ac3_delay=-1;

RESULT eAMLTSMPEGDecoder::setHwPCMDelay(int delay)
{
	TRACE__
	return 0;
}

RESULT eAMLTSMPEGDecoder::setHwAC3Delay(int delay)
{
	TRACE__
	return 0;
}


RESULT eAMLTSMPEGDecoder::setPCMDelay(int delay)
{
	TRACE__
	return m_decoder == 0 ? setHwPCMDelay(delay) : -1;
}

RESULT eAMLTSMPEGDecoder::setAC3Delay(int delay)
{
	TRACE__
	return m_decoder == 0 ? setHwAC3Delay(delay) : -1;
}


RESULT eAMLTSMPEGDecoder::setVideoPID(int vpid, int type)
{
	TRACE__
	if ((m_vpid != vpid) || (m_vtype != type))
	{
		m_changed |= changeVideo;
		m_vpid = vpid;
		m_vtype = type;
		m_codec.video_type = VFORMAT_MPEG12;
		switch (type)
		{
		default:
		case MPEG2:
		case MPEG1:
			eDebug("%s() video type: MPEG1/2",__PRETTY_FUNCTION__);
			break;
		case MPEG4_H264:
			m_codec.video_type = VFORMAT_H264;
			eDebug("%s() video type: MPEG4 H264",__PRETTY_FUNCTION__);
			break;
		case MPEG4_Part2:
			m_codec.video_type = VFORMAT_MPEG4; //maybe?
			eDebug("%s() video type: MPEG4 Part2",__PRETTY_FUNCTION__);
			break;
		}
		eDebug("%s() vpid=%d, type=%d",__PRETTY_FUNCTION__, vpid, type);
	}
	return 0;
}

RESULT eAMLTSMPEGDecoder::setAudioPID(int apid, int type)
{
	TRACE__			
	/* do not set an audio pid on decoders without audio support */
	if ((m_apid != apid) || (m_atype != type))
	{
		m_changed |= changeAudio;
		m_atype = type;
		m_apid = apid;
		
		m_codec.audio_type = AFORMAT_MPEG;
		switch (type)
		{
		default:
		case aMPEG:
			eDebug("%s() audio type: MPEG",__PRETTY_FUNCTION__);
			break;
		case aAC3:
			m_codec.audio_type = AFORMAT_AC3;
			eDebug("%s() audio type: AC3",__PRETTY_FUNCTION__);
			break;
		case aAAC:
			m_codec.audio_type = AFORMAT_AAC;
			eDebug("%s() audio type: AAC",__PRETTY_FUNCTION__);
			break;
		case aDTS:
			m_codec.audio_type = AFORMAT_DTS;
			eDebug("%s() audio type: DTS",__PRETTY_FUNCTION__);
			break;
		case aAACHE:
			m_codec.audio_type = AFORMAT_AAC_LATM;
			eDebug("%s() audio type: AAC_LATM",__PRETTY_FUNCTION__);
			break;

		}
		eDebug("%s() apid=%d, type=%d",__PRETTY_FUNCTION__, apid, type);
		
		if (aml_fd >= 0 ) {
			
			audio_decode_stop(adec_handle);
			audio_decode_release(&adec_handle);
			
			if(::ioctl(aml_fd, AMSTREAM_IOC_AID, 0xffff) < 0)
			{
				eDebug("[eAMLTSMPEGDecoder::play] set audio PID failed");					
			}
			
					
			if(::ioctl(aml_fd, AMSTREAM_IOC_AFORMAT, m_codec.audio_type) < 0)
			{
				eDebug("[eAMLTSMPEGDecoder::play] set audio format failed");						
			}				
			if(::ioctl(aml_fd, AMSTREAM_IOC_AID, m_apid) < 0)
			{
				eDebug("[eAMLTSMPEGDecoder::play] set audio PID failed");					
			}
			
			if(::ioctl(aml_fd, AMSTREAM_IOC_SAMPLERATE,48000) < 0)
			{
				eDebug("[eAMLTSMPEGDecoder::play] set AMSTREAM_IOC_SAMPLERATE failed");					
			}
			if(::ioctl(aml_fd, AMSTREAM_IOC_ACHANNEL, 2) < 0)
			{
				eDebug("[eAMLTSMPEGDecoder::play] set AMSTREAM_IOC_ACHANNEL failed");					
			}
										
			/*reset audio*/
			if(::ioctl(aml_fd, AMSTREAM_IOC_AUDIO_RESET, 0) < 0)
			{
				eDebug("[eAMLTSMPEGDecoder::play] audio reset failed");				
			}
			
			audio_decode_init(&adec_handle, &am_param);							
		}
	}
	return 0;
}

int eAMLTSMPEGDecoder::m_audio_channel = -1;

RESULT eAMLTSMPEGDecoder::setAudioChannel(int channel)
{
	TRACE__
	if (channel == -1)
	channel = ac_stereo;
	return 0;
}

int eAMLTSMPEGDecoder::getAudioChannel()
{
	TRACE__
	return m_audio_channel == -1 ? ac_stereo : m_audio_channel;
}

RESULT eAMLTSMPEGDecoder::setSyncPCR(int pcrpid)
{
	TRACE__
	eDebug("eAMLTSMPEGDecoder::setSyncPCR %d",pcrpid);
	m_pcrpid = pcrpid;
	return 0;
}

RESULT eAMLTSMPEGDecoder::setTextPID(int textpid)
{
	TRACE__
	eDebug("%s() m_textpid=%d",__PRETTY_FUNCTION__, textpid);
	return 0;
}

RESULT eAMLTSMPEGDecoder::setSyncMaster(int who)
{
	TRACE__
	return 0;
}

RESULT eAMLTSMPEGDecoder::set()
{
	TRACE__
	return 0;
}

int eAMLTSMPEGDecoder::osdBlank(char *path,int cmd)
{
	int fd;
	char  bcmd[16];
	fd = ::open(path, O_CREAT|O_RDWR | O_TRUNC, 0644);

	if(fd >=0 ) {
		sprintf(bcmd,"%d",cmd);
		write(fd,bcmd,strlen(bcmd));
		close(fd);
		return 0;
	}

	return -1;
}

int eAMLTSMPEGDecoder::setAvsyncEnable(int enable)
{
	int fd;
	char *path = "/sys/class/tsync/enable";
	char  bcmd[16];
	fd = ::open(path, O_CREAT | O_RDWR | O_TRUNC, 0644);
	if (fd >= 0) {
		sprintf(bcmd, "%d", enable);
		write(fd, bcmd, strlen(bcmd));
		close(fd);
		return 0;
	}

	return -1;
}

int eAMLTSMPEGDecoder::setSyncMode(int mode)
{
	int fd;
	char *path = "/sys/class/tsync/mode";
	char  bcmd[16];
	fd = ::open(path, O_CREAT | O_RDWR | O_TRUNC, 0644);
	if (fd >= 0) {
		sprintf(bcmd, "%d", mode);
		write(fd, bcmd, strlen(bcmd));
		close(fd);
		printf("set sync mode to %d!\n", mode);
		return 0;
	}
	return -1;
}
RESULT eAMLTSMPEGDecoder::play()
{
	TRACE__
	int ret;
	
	if (m_state == stateStop)
	{
		if ( ((m_apid >= 0) && (m_apid < 0x1FFF)) &&
				(((m_vpid >= 0) && (m_vpid < 0x1FFF)) || m_radio_pic.length()))
		{

			/* reuse osdBlank for blackout_policy test    */
			/* arg. value:				      */
			/*  1 - on channel change put black frame     */
			/*  0 - on channel change keep previous frame */		
			osdBlank("/sys/class/video/blackout_policy", 0);
			
			if(m_radio_pic.length())
			showSinglePic(m_radio_pic.c_str());
			
			if (m_radio_pic_on)
			finishShowSinglePic();
			
			if ((m_vpid >= 0) && (m_vpid < 0x1FFF))	
			osdBlank("/sys/class/video/blackout_policy", 1);				
			

			aml_fd = ::open("/dev/amstream_mpts",  O_RDWR);
			if(aml_fd < 0)
			{
				eDebug("[eAMLTSMPEGDecoder::play] Amlogic CODEC open failed  !!!!!");
			}
			else
			{
				eDebug("[eAMLTSMPEGDecoder::play] Amlogic CODEC open success !!!!!");									
				
			
				setAvsyncEnable(m_demux ? (m_demux->getSource() == -1 ? 1 : 0) : 0);
				
				if ((m_vpid >= 0) && (m_vpid < 0x1FFF))	 
				{									
					if(::ioctl(aml_fd, AMSTREAM_IOC_VFORMAT, m_codec.video_type) < 0)
					{
						eDebug("[eAMLTSMPEGDecoder::play] set video format failed");						
					}					
					if(::ioctl(aml_fd, AMSTREAM_IOC_VID, m_vpid) < 0)
					{
						eDebug("[eAMLTSMPEGDecoder::play] set video PID failed");					
					}
					if(::ioctl(aml_fd, AMSTREAM_IOC_SYSINFO, (unsigned long)&am_sysinfo) < 0)
					{
						eDebug("[eAMLTSMPEGDecoder::play] set AMSTREAM_IOC_SYSINFO failed");					
					}
				}
				if ((m_apid >= 0) && (m_apid < 0x1FFF)) 
				{
					if(::ioctl(aml_fd, AMSTREAM_IOC_AFORMAT, m_codec.audio_type) < 0)
					{
						eDebug("[eAMLTSMPEGDecoder::play] set audio format failed");						
					}
					
					if(::ioctl(aml_fd, AMSTREAM_IOC_AID, m_apid) < 0)
					{
						eDebug("[eAMLTSMPEGDecoder::play] set audio PID failed");					
					}
					
					if(::ioctl(aml_fd, AMSTREAM_IOC_SAMPLERATE,48000) < 0)
					{
						eDebug("[eAMLTSMPEGDecoder::play] set AMSTREAM_IOC_SAMPLERATE failed");					
					}
					if(::ioctl(aml_fd, AMSTREAM_IOC_ACHANNEL, 2) < 0)
					{
						eDebug("[eAMLTSMPEGDecoder::play] set AMSTREAM_IOC_ACHANNEL failed");					
					}
				}
				if ((m_pcrpid >= 0) && (m_pcrpid < 0x1FFF)) 
				{
					if(::ioctl(aml_fd, AMSTREAM_IOC_PCRID, m_pcrpid) < 0)
					{
						eDebug("[eAMLTSMPEGDecoder::play] set PCR PID failed");						
					}
				}
			
				
				/* Tell the kernel on which adapter we want HW CSA/LiveTV */
				if(::ioctl(aml_fd, AMSTREAM_IOC_SET_DEMUX, (unsigned long) (m_demux ? (m_demux->getSource() == -1 ? 2 : m_demux->getSource()) : 0)) < 0)
				{
					eDebug("[eAMLTSMPEGDecoder::play] set AMSTREAM_IOC_SET_DEMUX failed");						
				}
				
				am_param.channels = 2;
				am_param.sample_rate = 48000;
				am_param.handle = aml_fd;
				am_param.format = m_codec.audio_type;
				audio_decode_init(&adec_handle, &am_param);
	
				if (cntl_fd >= 0 && m_demux && m_demux->getSource() != -1) {
						if(::ioctl(cntl_fd, AMSTREAM_IOC_AVTHRESH, (unsigned long)90000 * 30 ) < 0)
							eDebug("[eAMLTSMPEGDecoder::play] set AMSTREAM_IOC_AVTHRESH failed");
						if(::ioctl(cntl_fd, AMSTREAM_IOC_SYNCTHRESH, (unsigned long) 0) < 0)
							eDebug("[eAMLTSMPEGDecoder::play] set AMSTREAM_IOC_SYNCTHRESH failed");							
				} else
						eDebug("[eAMLTSMPEGDecoder::play] cntl_fd NULL or PVR mode");

				if(::ioctl(aml_fd, AMSTREAM_IOC_PORT_INIT, 0) < 0)
				{
					eDebug("[eAMLTSMPEGDecoder::play] amport init failed");				
				}				
				if(::ioctl(aml_fd, AMSTREAM_IOC_TS_SKIPBYTE, 0) < 0)
				{
					eDebug("[eAMLTSMPEGDecoder::play] set ts skipbyte failed");				
				}									
				m_state = statePlay;												
			}					
		}
		else
		{
			eDebug("[eAMLTSMPEGDecoder::play] Invalid PIDs given I refuse to start !!!!!");
		}
	}
	else if (m_state == statePause) {

		audio_decode_resume(adec_handle);
		
		if ((m_vpid >= 0) && (m_vpid < 0x1FFF))	 
			::ioctl(aml_fd, AMSTREAM_IOC_VPAUSE, 0);
		
		if (m_demux && m_demux->m_pvr_fd >= 0)
			::ioctl(m_demux->m_pvr_fd, PVR_P3);
				
		m_state = statePlay;
	}
	return 0;
}

RESULT eAMLTSMPEGDecoder::pause()
{
	TRACE__
	struct adec_status adec;
	int len = 0;
	int i;
	
	if (m_state == statePause)
	return 0;
	
	if (m_demux && m_demux->m_pvr_fd >= 0)
		::ioctl(m_demux->m_pvr_fd, PVR_P0);
		
	audio_decode_pause(adec_handle);
        
	if ((m_vpid >= 0) && (m_vpid < 0x1FFF))	 
		::ioctl(aml_fd, AMSTREAM_IOC_VPAUSE, 1);
			
	m_state = statePause;
	return 0;
}

RESULT eAMLTSMPEGDecoder::setFastForward(int frames_to_skip)
{
	TRACE__
	// fast forward is only possible if video data is present
	if (!m_codec.has_video)
	return -1;
	
	return 0;
}

RESULT eAMLTSMPEGDecoder::setSlowMotion(int repeat)
{
	TRACE__
	// slow motion is only possible if video data is present
	if (!m_codec.has_video)
	return -1;
	
	return 0;
}

RESULT eAMLTSMPEGDecoder::setTrickmode()
{
	TRACE__
	if (!m_codec.has_video)
	return -1;
	
	return 0;
}

RESULT eAMLTSMPEGDecoder::flush()
{
	TRACE__
	return 0;
}

void eAMLTSMPEGDecoder::demux_event(int event)
{
	TRACE__
	switch (event)
	{
	case eDVBDemux::evtFlush:
		flush();
		break;
	default:
		break;
	}
}

RESULT eAMLTSMPEGDecoder::getPTS(int what, pts_t &pts)
{
	unsigned int aml_pts;
	
	if (what == 0) /* auto */
		what = ((m_vpid >= 0) && (m_vpid < 0x1FFF)) ? 1 : 2;

	if (what == 1) /* video */
	{		
		if(::ioctl(aml_fd, AMSTREAM_IOC_VPTS, (unsigned long)&aml_pts) >= 0) 
		{
			pts = aml_pts;
			return 0;
		}
	}

	if (what == 2) /* audio */
	{			
		if(::ioctl(aml_fd, AMSTREAM_IOC_APTS, (unsigned long)&aml_pts) >= 0) 
		{
			pts = aml_pts;
			return 0;
		}
	}
	return -1;
}

RESULT eAMLTSMPEGDecoder::setRadioPic(const std::string &filename)
{
	TRACE__
	m_radio_pic = filename;
	return 0;
}

RESULT eAMLTSMPEGDecoder::showSinglePic(const char *filename)
{
	TRACE__

	if (m_decoder == 0)
	{
		eDebug("showSinglePic %s", filename);
		int f = open(filename, O_RDONLY);
		if (f >= 0)
		{
			int ret;
			struct stat s;
			fstat(f, &s);
#if defined(__sh__) // our driver has a different behaviour for iframes
			if (m_video_clip_fd >= 0)
			finishShowSinglePic();
#endif

			m_codec.has_video = 1;	
			m_codec.has_audio = 0;	
			m_codec.stream_type = STREAM_TYPE_ES_VIDEO;
			ret = codec_init(&m_codec);
			if(ret == CODEC_ERROR_NONE)		
			{
				bool seq_end_avail = false;
				size_t pos=0;
				unsigned char pes_header[] = { 0x00, 0x00, 0x01, 0xE0, 0x00, 0x00, 0x80, 0x80, 0x05, 0x21, 0x00, 0x01, 0x00, 0x01 };
				unsigned char seq_end[] = { 0x00, 0x00, 0x01, 0xB7 };
				unsigned char iframe[s.st_size];
				unsigned char stuffing[8192];
				int streamtype;
				memset(stuffing, 0, 8192);
				read(f, iframe, s.st_size);
				
				setAvsyncEnable(0);
				m_radio_pic_on = 1;
				
				while(pos <= (s.st_size-4) && !(seq_end_avail = (!iframe[pos] && !iframe[pos+1] && iframe[pos+2] == 1 && iframe[pos+3] == 0xB7)))
				++pos;
				if ((iframe[3] >> 4) != 0xE) // no pes header
				writeAll(m_codec.handle, pes_header, sizeof(pes_header));
				else
				iframe[4] = iframe[5] = 0x00;
				writeAll(m_codec.handle, iframe, s.st_size);
				if (!seq_end_avail)
				write(m_codec.handle, seq_end, sizeof(seq_end));
				writeAll(m_codec.handle, stuffing, 8192);
#if not defined(__sh__)
				m_showSinglePicTimer->start(150, true);
#endif		
			}
			close(f);
		}
		else
		{
			eDebug("couldnt open %s", filename);
			return -1;
		}
	}
	else
	{
		eDebug("only show single pics on first decoder");
		return -1;
	}

	return 0;
}

void eAMLTSMPEGDecoder::finishShowSinglePic()
{
	TRACE__
	int ret;
	struct buf_status vbuf;
	
	if (m_codec.handle >= 0 && m_radio_pic_on) {
		do {
			ret = codec_get_vbuf_state(&m_codec, &vbuf);
			if (ret != 0) 				
			goto error;		
		} while (vbuf.data_len > 0x100);
error:
		usleep(200000);
		codec_close(&m_codec);		
		m_radio_pic_on = 0;
	}
}

void eAMLTSMPEGDecoder::parseVideoInfo()
{
	if (m_width == -1 && m_height == -1)
	{	
		int x, y;
		CFile::parseIntHex(&x, "/proc/stb/vmpeg/0/xres");
		CFile::parseIntHex(&y, "/proc/stb/vmpeg/0/yres");
		
		if ( x > 0 && y > 0) {
			struct iTSMPEGDecoder::videoEvent event;
			CFile::parseInt(&m_aspect, "/proc/stb/vmpeg/0/aspect");				
			event.type = iTSMPEGDecoder::videoEvent::eventSizeChanged;
			m_aspect = event.aspect = m_aspect == 1 ? 2 : 3;  // convert dvb api to etsi
			m_height = event.height = y;
			m_width = event.width = x;
			video_event(event);			
		}
	}
	else if (m_width > 0 && m_framerate == -1)	
	{
		struct iTSMPEGDecoder::videoEvent event;
		CFile::parseInt(&m_framerate, "/proc/stb/vmpeg/0/framerate");			
		event.type = iTSMPEGDecoder::videoEvent::eventFrameRateChanged;
		event.framerate = m_framerate;
		video_event(event);		
	}
	else if (m_width > 0 && m_progressive == -1) 
	{		
		CFile::parseIntHex(&m_progressive, "/proc/stb/vmpeg/0/progressive");
		if (m_progressive != 2)
		{
			struct iTSMPEGDecoder::videoEvent event;
			event.type = iTSMPEGDecoder::videoEvent::eventProgressiveChanged;
			event.progressive = m_progressive;
			video_event(event);
		}
	}	
}

RESULT eAMLTSMPEGDecoder::connectVideoEvent(const Slot1<void, struct videoEvent> &event, ePtr<eConnection> &conn)
{
	TRACE__
	conn = new eConnection(this, m_video_event.connect(event));
	return 0;
}

void eAMLTSMPEGDecoder::video_event(struct videoEvent event)
{
	TRACE__
	/* emit */ m_video_event(event);
}

int eAMLTSMPEGDecoder::getVideoWidth()
{
	TRACE__
	int m_width = -1;
	CFile::parseIntHex(&m_width, "/proc/stb/vmpeg/0/xres");
	if (!m_width)
	return -1;
	eDebug("couldnt open %d", m_width);
	return m_width;
}

int eAMLTSMPEGDecoder::getVideoHeight()
{
	TRACE__
	int m_height = -1;
	CFile::parseIntHex(&m_height, "/proc/stb/vmpeg/0/yres");
	if (!m_height)
	return -1;
	return m_height;
}

int eAMLTSMPEGDecoder::getVideoProgressive()
{
	TRACE__
	int m_progressive = -1;
	CFile::parseIntHex(&m_progressive, "/proc/stb/vmpeg/0/progressive");
	if (m_progressive == 2)
	return -1;
	return m_progressive;
}

int eAMLTSMPEGDecoder::getVideoFrameRate()
{
	TRACE__
	int m_framerate = -1;
	CFile::parseInt(&m_framerate, "/proc/stb/vmpeg/0/framerate");
	return m_framerate;
}

int eAMLTSMPEGDecoder::getVideoAspect()
{
	TRACE__
	int m_aspect = -1;
	CFile::parseInt(&m_aspect, "/proc/stb/vmpeg/0/aspect");
	if (!m_aspect)
	return -1;
	
	return m_aspect == 1 ? 2 : 3;
}
